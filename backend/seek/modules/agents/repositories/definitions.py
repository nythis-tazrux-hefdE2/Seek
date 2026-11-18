from __future__ import annotations

import copy
from types import SimpleNamespace

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from seek.modules.agents.models.definitions import Agent
from seek.modules.agents.permissions import is_builtin_agent, user_can_access_agent, user_can_run_agent
from seek.modules.agents.presets import AgentPreset
from seek.modules.agents.presets.ai_intelligence import PRESET as DEFAULT_AGENT
from seek.modules.identity.models import User
from seek.shared.datetime import utc_now

DEFAULT_AGENT_SLUG = DEFAULT_AGENT.slug
DEFAULT_AGENT_NAME = DEFAULT_AGENT.name
DEFAULT_AGENT_BACKEND_ID = DEFAULT_AGENT.backend_id
DEFAULT_AGENT_DESCRIPTION = DEFAULT_AGENT.description
DEFAULT_SHARE_CONFIG = {
    "version": 2,
    "read_scope": {"access_level": "global", "department_ids": [], "user_uids": []},
    "manage_scope": None,
}


class AgentRepository:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def ensure_default_agent(self, *, created_by: str | None = None) -> tuple[Agent, bool]:
        """准备内置默认定义并返回是否修改，由用例提交。"""
        agent = await self.get_by_slug(DEFAULT_AGENT_SLUG)
        if agent:
            needs_update = False
            if agent.share_config != DEFAULT_SHARE_CONFIG:
                agent.share_config = DEFAULT_SHARE_CONFIG.copy()
                needs_update = True
            if not agent.description:
                agent.description = DEFAULT_AGENT_DESCRIPTION
                needs_update = True
            if not agent.is_default:
                return await self.set_default(agent=agent, updated_by=created_by), True
            if needs_update:
                agent.updated_by = created_by
                agent.updated_at = utc_now()
            return agent, needs_update

        agent = Agent(
            slug=DEFAULT_AGENT_SLUG,
            backend_id=DEFAULT_AGENT_BACKEND_ID,
            name=DEFAULT_AGENT_NAME,
            description=DEFAULT_AGENT_DESCRIPTION,
            icon=None,
            pics=[],
            config_json={"context": copy.deepcopy(DEFAULT_AGENT.context)},
            share_config=DEFAULT_SHARE_CONFIG.copy(),
            visibility="shared",
            is_builtin=True,
            is_default=True,
            created_by=created_by,
            updated_by=created_by,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.db.add(agent)
        return agent, True

    async def ensure_preset(self, preset: AgentPreset, *, created_by: str | None = None) -> tuple[Agent, bool]:
        """返回预置定义及是否修改，保留已存在的用户配置。"""
        if preset.slug == DEFAULT_AGENT_SLUG:
            return await self.ensure_default_agent(created_by=created_by)
        agent = await self.get_by_slug(preset.slug)
        if agent:
            return agent, False

        agent = Agent(
            slug=preset.slug,
            backend_id=preset.backend_id,
            name=preset.name,
            description=preset.description,
            icon=None,
            pics=[],
            config_json={"context": copy.deepcopy(preset.context)},
            share_config=DEFAULT_SHARE_CONFIG.copy(),
            visibility="shared",
            is_builtin=True,
            is_default=False,
            created_by=created_by,
            updated_by=created_by,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.db.add(agent)
        return agent, True

    async def list_visible(self, *, user: User) -> list[Agent]:
        """列出当前用户可见的智能体配置。"""
        visibility_user = await self._visibility_user(user)
        if visibility_user is None:
            return []
        stmt = select(Agent)
        result = await self.db.execute(stmt.order_by(Agent.is_default.desc(), Agent.id.asc()))
        agents = list(result.scalars().all())
        if visibility_user.role == "superadmin":
            return agents
        return [
            agent
            for agent in agents
            if (getattr(user, "user_kind", "human") != "end_user" or agent.visibility == "shared")
            and user_can_access_agent(visibility_user, agent)
        ]

    async def get_by_slug(self, slug: str, *, for_key_share: bool = False) -> Agent | None:
        """读取 Agent，创建 Thread 时可持有共享键锁直到提交。"""
        statement = select(Agent).where(Agent.slug == slug)
        if for_key_share:
            statement = statement.with_for_update(read=True, key_share=True).execution_options(populate_existing=True)
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def get_visible_by_slug(
        self,
        *,
        slug: str,
        user: User,
        for_key_share: bool = False,
        for_run: bool = True,
    ) -> Agent | None:
        """按 slug 读取并校验当前调用者的智能体权限。"""
        visibility_user = await self._visibility_user(user)
        if visibility_user is None:
            return None
        agent = await self.get_by_slug(slug, for_key_share=for_key_share)
        if not agent:
            return None
        if getattr(user, "user_kind", "human") == "end_user" and agent.visibility != "shared":
            return None
        if for_run and agent.visibility == "private" and not user_can_run_agent(user, agent):
            return None
        if not user_can_access_agent(visibility_user, agent):
            return None
        return agent

    async def _visibility_user(self, user: User) -> User | None:
        """终端用户只借用 Key 用户的 Agent 可见性，执行 UID 保持不变。"""
        if user is None or user.is_deleted:
            return None
        if getattr(user, "user_kind", "human") != "end_user":
            return user
        owner = await self.db.scalar(
            select(User).where(
                User.id == user.owner_user_id,
                User.user_kind == "human",
                User.is_deleted == 0,
            )
        )
        if owner is None or user.is_deleted:
            return None
        return SimpleNamespace(uid=owner.uid, department_id=owner.department_id, role="user", is_deleted=0)

    async def set_default(self, *, agent: Agent, updated_by: str | None = None) -> Agent:
        if agent.visibility != "shared":
            raise ValueError("默认 Agent 必须为共享状态")
        if not is_builtin_agent(agent):
            raise ValueError("默认智能体已固定为内置智能助手")
        share_config = agent.share_config or DEFAULT_SHARE_CONFIG.copy()
        read_scope = share_config.get("read_scope") or {}
        if read_scope.get("access_level") != "global":
            raise ValueError("内置智能体必须全局共享")

        now = utc_now()
        await self.db.execute(update(Agent).where(Agent.is_default.is_(True)).values(is_default=False, updated_at=now))
        agent.is_default = True
        agent.updated_by = updated_by
        agent.updated_at = now
        await self.db.flush()
        return agent
