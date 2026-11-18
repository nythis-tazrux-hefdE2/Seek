"""研究配置的授权读取与元数据装配。"""

from typing import Any

from seek.infrastructure.observability.logging import logger
from seek.modules.agents.models.definitions import Agent
from seek.modules.agents.permissions import is_builtin_agent, user_can_manage_agent, user_can_run_agent
from seek.modules.agents.repositories.definitions import AgentRepository
from seek.modules.agents.runtime.agent_backends import AgentBackendNotFoundError, get_agent_backend
from seek.modules.agents.runtime.context import filter_declared_config
from seek.modules.identity.models import User
from seek.modules.identity.permissions import normalize_permission_config, resolve_agent_permission
from seek.modules.identity.permissions.resource_permission import ADMIN_ROLES
from seek.shared.errors import ResourceNotFoundError


async def ensure_default_agent_definition(db, *, created_by: str | None = None) -> Agent:
    """默认定义变化时提交，读取已就绪定义不产生空提交。"""
    agent, changed = await AgentRepository(db).ensure_default_agent(created_by=created_by)
    if changed:
        await db.commit()
    return agent


async def serialize_agent_definition(
    db,
    agent: Agent,
    *,
    user: User,
    include_configurable_items: bool = False,
    backend_info_cache: dict[tuple[str, bool, str], dict] | None = None,
) -> dict[str, Any]:
    """装配治理权限、后端元数据与配置项。"""
    data = agent.to_dict()
    data["share_config_invalid"] = False
    try:
        data["share_config"] = normalize_permission_config(agent.share_config)
    except (TypeError, ValueError) as exc:
        if user.role != "superadmin":
            raise
        # 管理者需要读取原始坏配置进行修复，不将它解释为有效共享范围。
        data["share_config"] = agent.share_config
        data["share_config_invalid"] = True
        logger.warning("Invalid agent share config exposed for repair: slug={}, error={}", agent.slug, str(exc))
    permission = resolve_agent_permission(user, agent)
    is_builtin = is_builtin_agent(agent)
    data["can_manage"] = user_can_manage_agent(user, agent)
    data["can_run"] = user_can_run_agent(user, agent)
    data["can_share"] = data["can_manage"] and not is_builtin and (agent.visibility == "shared" or user.role in ADMIN_ROLES)
    data["can_transfer"] = agent.visibility == "shared" and user.role == "superadmin" and not is_builtin
    data["effective_permission"] = permission.value
    data["is_builtin"] = is_builtin
    data["permission_locked"] = is_builtin

    try:
        backend = get_agent_backend(agent.backend_id)
    except AgentBackendNotFoundError as exc:
        raise ResourceNotFoundError(str(exc)) from exc
    data["config_json"] = filter_declared_config(data.get("config_json") or {}, context_schema=backend.context_schema)
    cache_key = (agent.backend_id, include_configurable_items, user.role)
    backend_info = backend_info_cache.get(cache_key) if backend_info_cache is not None else None
    if backend_info is None:
        backend_info = await backend.get_info(
            include_configurable_items=include_configurable_items,
            user_role=user.role,
            db=db if include_configurable_items else None,
            user=user if include_configurable_items else None,
        )
        if backend_info_cache is not None:
            backend_info_cache[cache_key] = backend_info
    data["metadata"] = backend_info.get("metadata", {})
    if include_configurable_items:
        data["configurable_items"] = backend_info.get("configurable_items", {})
    return data


async def list_visible_agent_definitions(db, *, user: User) -> list[Agent]:
    """返回当前用户可见 Agent，并确保默认定义已就绪。"""
    await ensure_default_agent_definition(db)
    return await AgentRepository(db).list_visible(user=user)


async def get_visible_agent_definition(db, *, user: User, slug: str) -> Agent | None:
    """按运行期可见性读取 Agent；不存在或不可见返回 None。"""
    return await AgentRepository(db).get_visible_by_slug(slug=slug, user=user, for_run=False)


async def get_agent_definition_by_slug(db, *, slug: str) -> Agent | None:
    """按标识读取 Agent 定义，供只读管理入口使用。"""
    return await AgentRepository(db).get_by_slug(slug)
