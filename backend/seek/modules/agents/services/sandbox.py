"""用户设置的环境状态与重建用例。"""

import asyncio

from seek.modules.agents.runtime.sandbox import get_sandbox_provider


async def get_user_sandbox(uid: str) -> dict:
    """读取控制状态，不唤醒环境。"""
    return await asyncio.to_thread(get_sandbox_provider().status, uid)
