from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from seek.modules.agents.presets import discover_agent_presets
from seek.modules.agents.runtime.agent_backends import get_agent_backend


async def initialize_agent_presets(db: AsyncSession) -> None:
    """确认所有角色后端存在，再按既有落库规则初始化。"""
    from seek.modules.agents.repositories.definitions import AgentRepository

    presets = discover_agent_presets()
    for preset in presets:
        get_agent_backend(preset.backend_id)
    repository = AgentRepository(db)
    changed = False
    for preset in presets:
        _, updated = await repository.ensure_preset(preset)
        changed = changed or updated
    if changed:
        await db.commit()
