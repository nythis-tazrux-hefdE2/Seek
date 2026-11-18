"""装配唯一的 container 执行客户端。"""

from __future__ import annotations

import asyncio
import os

from seek.modules.agents.runtime.sandbox.container import ContainerSandboxProvider

_sandbox_provider: ContainerSandboxProvider | None = None


def get_sandbox_provider() -> ContainerSandboxProvider:
    """客户端不持有 Docker socket，运行归属仍由 PG 校验。"""
    global _sandbox_provider
    if _sandbox_provider is None:
        validate_sandbox_configuration()
        _sandbox_provider = ContainerSandboxProvider()
    return _sandbox_provider


async def check_sandbox_provider() -> None:
    """确认 runner、数据库和固定镜像实际就绪。"""
    await asyncio.to_thread(get_sandbox_provider().health)


def validate_sandbox_configuration() -> None:
    """部署必须提供独立 runner 凭据。"""
    if len(os.environ.get("SANDBOX_RUNNER_TOKEN", "").strip()) < 16:
        raise RuntimeError("SANDBOX_RUNNER_TOKEN 需要至少 16 个字符")
