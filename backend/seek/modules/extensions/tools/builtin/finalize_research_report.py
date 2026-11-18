"""校验并交付本次研究的唯一正式格式。"""

import json
from typing import Annotated, Any

from langchain.tools import InjectedToolCallId
from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolArg
from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.types import Command

from seek.infrastructure.postgres.manager import pg_manager
from seek.modules.agents.research_reports import FinalizeResearchReportInput, ResearchReport
from seek.modules.agents.services.research_reports import finalize_report
from seek.modules.extensions.tools.registry import tool


class ResearchReportToolInput(FinalizeResearchReportInput):
    """框架注入字段参与内部校验，但不进入模型可见 schema。"""

    runtime: Annotated[Any, InjectedToolArg]
    tool_call_id: Annotated[str, InjectedToolCallId]


@tool(
    category="builtin",
    display_name="生成正式研究报告",
    args_schema=ResearchReportToolInput,
    description=(
        "使用本次精确调研任务和独立核查结果校验来源、日期、摘录，生成并展示 HTML。"
        "review_input_id 对应的最终回答必须是 ResearchReview JSON。"
        "失败时修正内容或补充研究，不能声称交付完成。"
    ),
)
async def finalize_research_report(
    report: ResearchReport,
    research_input_ids: list[str],
    review_input_id: str,
    runtime: ToolRuntime,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """调用方身份从可信 runtime 取得，不接受模型替换。"""
    try:
        async with pg_manager.get_async_session_context() as db:
            result = await finalize_report(
                db=db,
                context=runtime.context,
                tool_call_id=tool_call_id,
                report=report,
                research_input_ids=research_input_ids,
                review_input_id=review_input_id,
            )
    except ValueError as exc:
        return Command(update={"messages": [ToolMessage(content=str(exc), tool_call_id=tool_call_id, status="error")]})
    return Command(
        update={
            "artifacts": [result["path"]],
            "messages": [
                ToolMessage(content=json.dumps(result, ensure_ascii=False), artifact={"research_report": result}, tool_call_id=tool_call_id)
            ],
        }
    )
