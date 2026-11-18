"""固定研究配置的只读目录。"""

from fastapi import APIRouter, Depends, HTTPException

from seek.api.dependencies.auth import get_db, get_required_user
from seek.modules.agents.permissions import user_can_access_agent
from seek.modules.agents.services.definitions import (
    ensure_default_agent_definition,
    get_visible_agent_definition,
    list_visible_agent_definitions,
    serialize_agent_definition,
)

agent_router = APIRouter(prefix="/agent", tags=["agent"])


@agent_router.get("")
async def list_agents(user=Depends(get_required_user), db=Depends(get_db)):
    """返回用户可运行的固定研究配置。"""
    return {
        "agents": [await serialize_agent_definition(db, item, user=user) for item in await list_visible_agent_definitions(db, user=user)]
    }


@agent_router.get("/default")
async def get_default_agent(user=Depends(get_required_user), db=Depends(get_db)):
    """读取已初始化的默认研究入口。"""
    item = await ensure_default_agent_definition(db)
    if not user_can_access_agent(user, item):
        raise HTTPException(404, "默认研究配置不可访问")
    return {"agent": await serialize_agent_definition(db, item, user=user)}


@agent_router.get("/{agent_id}")
async def get_agent(agent_id: str, user=Depends(get_required_user), db=Depends(get_db)):
    """读取授权研究配置，不能编辑引擎或安装资源。"""
    item = await get_visible_agent_definition(db, user=user, slug=agent_id)
    if item is None:
        raise HTTPException(404, "研究配置不存在")
    return {"agent": await serialize_agent_definition(db, item, user=user)}
