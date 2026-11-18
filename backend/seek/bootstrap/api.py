"""API 进程启动组件、readiness 状态与资源关闭适配。"""

import inspect
from collections.abc import Callable

from fastapi import FastAPI

from seek import get_version
from seek.infrastructure.observability.logging import logger
from seek.infrastructure.postgres.manager import pg_manager
from seek.infrastructure.postgres.schema import require_current_schema
from seek.modules.agents.runtime.sandbox import check_sandbox_provider
from seek.modules.agents.services.transport import get_redis_client
from seek.modules.identity.oidc import get_oidc_config
from seek.modules.identity.security import AuthUtils


class RequiredStartupComponentError(RuntimeError):
    """核心启动组件失败且当前进程不得继续接流量。"""

    def __init__(self, component: str, code: str):
        self.component = component
        self.code = code
        super().__init__(f"Required startup component failed: component={component}, type={code}")


async def startup(app: FastAPI) -> None:
    """取得 API 运行资源并发布结构化启动状态。"""

    app.state.startup_complete = False
    app.state.startup_components = {}

    await _initialize_startup_component(app, name="security_secrets", required=True, operation=AuthUtils.require_security_secrets)
    await _initialize_startup_component(app, name="oidc_config", required=True, operation=get_oidc_config)

    # 共享持久定义只由 Compose 中的 app-init 初始化；运行进程仅校验兼容版本。
    pg_manager.initialize()
    await require_current_schema(pg_manager)

    from seek.modules.system.options import system_options
    from seek.modules.system.services.options import invalidate_option_cache

    await invalidate_option_cache(system_options.key)

    await _initialize_startup_component(app, name="model_cache", required=True, operation=_initialize_model_cache)

    # 预热 Redis（run 队列）
    try:
        redis = await get_redis_client()
        await redis.ping()
    except Exception as exc:
        logger.warning(f"Run queue redis unavailable on startup: error_type={type(exc).__name__}")

    await _initialize_startup_component(app, name="sandbox_provider", required=True, operation=check_sandbox_provider)

    app.state.startup_complete = True
    logger.info("Seek backend startup complete: {}", get_version())


async def shutdown_component(name: str, operation: Callable[[], object]) -> None:
    """尽力释放一个已取得或部分取得的资源，并继续执行后续清理。"""

    try:
        await _run_operation(operation)
    except Exception as exc:
        logger.error(f"Shutdown component failed: component={name}, type={type(exc).__name__}")


async def _initialize_startup_component(app: FastAPI, *, name: str, required: bool, operation: Callable[[], object]) -> None:
    """执行启动组件并保存非敏感、可供 readiness 使用的能力状态。"""

    try:
        await _run_operation(operation)
    except Exception as exc:
        code = type(exc).__name__
        app.state.startup_components[name] = {"status": "error", "required": required, "code": code}
        logger.error(f"Startup component failed: component={name}, required={required}, type={code}")
        if required:
            raise RequiredStartupComponentError(name, code) from None
    else:
        app.state.startup_components[name] = {"status": "ok", "required": required}


async def _initialize_model_cache() -> None:
    """用 PostgreSQL 当前供应商事实重建进程内模型缓存（v2 模型选择使用）。"""

    from seek.modules.models.providers.cache import model_cache
    from seek.modules.models.providers.service import get_all_model_providers

    async with pg_manager.get_async_session_context() as session:
        providers = await get_all_model_providers(session)
        model_cache.rebuild(providers)


async def _run_operation(operation: Callable[[], object]) -> None:
    """执行同步或异步的组件操作。"""
    result = operation()
    if inspect.isawaitable(result):
        await result
