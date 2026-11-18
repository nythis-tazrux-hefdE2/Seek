"""从 PG 读取本次研究的任务因果关系与成功工具事实。"""

from sqlalchemy import select

from seek.modules.agents.models.inputs import AgentInput
from seek.modules.agents.models.messages import TOOL_AUDIT_MESSAGE_TYPE, Message
from seek.modules.agents.models.runs import AgentRun
from seek.modules.agents.models.sessions import Session
from seek.modules.agents.models.turns import AgentTurn
from seek.modules.agents.repositories.cooperation import CooperationRepository


class ResearchReportRepository:
    """报告查询受用户、APP、树和协调 Turn 的共同约束。"""

    def __init__(self, db):
        """借用调用方事务。"""
        self.db = db

    async def load_tasks(self, caller, root_turn_id: str, input_ids: list[str]):
        """沿真实派发关系求本轮后代，拒绝同树历史或别轮输入。"""
        members = select(Session.thread_id).where(
            Session.tree_root_thread_id == caller.tree_root_thread_id,
            Session.uid == caller.uid,
            Session.app_id == caller.app_id,
        )
        run_turns = dict((await self.db.execute(select(AgentRun.id, AgentRun.turn_id).where(AgentRun.thread_id.in_(members)))).all())
        inputs = list(
            (
                await self.db.scalars(
                    select(AgentInput).where(
                        AgentInput.thread_id.in_(members),
                        AgentInput.uid == caller.uid,
                        AgentInput.app_id == caller.app_id,
                        AgentInput.source == "cooperation",
                        AgentInput.channel == "internal",
                    )
                )
            ).all()
        )
        allowed_turns = {root_turn_id}
        allowed_inputs = set()
        changed = True
        while changed:
            changed = False
            for item in inputs:
                source_turn = run_turns.get((item.origin_metadata or {}).get("created_by_run_id"))
                if source_turn in allowed_turns and item.id not in allowed_inputs:
                    allowed_inputs.add(item.id)
                    if item.turn_id:
                        allowed_turns.add(item.turn_id)
                    changed = True
        if not set(input_ids).issubset(allowed_inputs):
            raise ValueError("研究任务不属于本次协调 Turn 的实际派发范围")
        return await CooperationRepository(self.db).task_rows(caller, input_ids=input_ids)

    async def successful_tool_messages(self, caller, turn_ids: set[str]) -> list[Message]:
        """只采精确任务最终 Run 与同作用域成功恢复链中的工具审计。"""
        chain = self._result_run_chain(uid=caller.uid, app_id=caller.app_id, turn_ids=turn_ids)
        return list(
            (
                await self.db.scalars(
                    select(Message)
                    .join(chain, (chain.c.id == Message.run_id) & (chain.c.turn_id == Message.turn_id))
                    .where(
                        Message.role == "tool",
                        Message.message_type == TOOL_AUDIT_MESSAGE_TYPE,
                        Message.execution_status == "completed",
                    )
                    .order_by(Message.id)
                )
            ).all()
        )

    async def published_reports(self, thread_id: str | None, uid: str, app_id: str | None) -> list[Message]:
        """从最终 Run 及同作用域显式恢复链读取成功检查，拒绝邻近执行段。"""
        chain = self._result_run_chain(uid=uid, app_id=app_id, thread_id=thread_id)
        return list(
            (
                await self.db.scalars(
                    select(Message)
                    .join(chain, (chain.c.id == Message.run_id) & (chain.c.turn_id == Message.turn_id))
                    .where(
                        Message.message_type == TOOL_AUDIT_MESSAGE_TYPE,
                        Message.execution_status == "completed",
                        Message.extra_metadata["tool_name"].as_string() == "finalize_research_report",
                    )
                )
            ).all()
        )

    def _result_run_chain(self, *, uid: str, app_id: str | None, thread_id: str | None = None, turn_ids: set[str] | None = None):
        """最终结果拥有可追溯的执行段；失败、取消和跨作用域节点中断取证。"""
        chain = (
            select(AgentRun.id, AgentRun.turn_id, AgentRun.thread_id, AgentRun.resume_from_run_id)
            .join(AgentTurn, AgentTurn.result_run_id == AgentRun.id)
            .where(
                AgentTurn.thread_id == thread_id if thread_id is not None else True,
                AgentTurn.id.in_(turn_ids) if turn_ids is not None else True,
                AgentTurn.uid == uid,
                AgentTurn.app_id == app_id,
                AgentTurn.status == "completed",
                AgentRun.turn_id == AgentTurn.id,
                AgentRun.thread_id == AgentTurn.thread_id,
                AgentRun.uid == uid,
                AgentRun.app_id == app_id,
                AgentRun.status == "completed",
            )
            .cte("final_result_runs", recursive=True)
        )
        # UNION 去重使坏数据中的环终止；拒绝的节点不会继续向前取证。
        return chain.union(
            select(AgentRun.id, AgentRun.turn_id, AgentRun.thread_id, AgentRun.resume_from_run_id)
            .join(chain, AgentRun.id == chain.c.resume_from_run_id)
            .where(
                AgentRun.turn_id == chain.c.turn_id,
                AgentRun.thread_id == chain.c.thread_id,
                AgentRun.uid == uid,
                AgentRun.app_id == app_id,
                AgentRun.status.in_(("completed", "interrupted", "yielded")),
            )
        )
