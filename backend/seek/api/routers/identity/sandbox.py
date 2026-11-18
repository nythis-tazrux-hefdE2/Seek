"""用户环境 Web 设置入口，不能由请求提供另一个 uid。"""

from fastapi import APIRouter, Depends

from seek.api.dependencies.auth import get_required_user
from seek.modules.agents.services.sandbox import get_user_sandbox
from seek.modules.identity.models import User

router = APIRouter(prefix="/user/sandbox", tags=["user"])


@router.get("")
async def get_sandbox(current_user: User = Depends(get_required_user)):
    """只返回当前认证用户的环境与占用。"""
    return await get_user_sandbox(str(current_user.uid))
