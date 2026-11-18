"""API 生命周期与失败补偿清理。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from seek.bootstrap.api import shutdown_component, startup
from seek.infrastructure.postgres.manager import pg_manager
from seek.infrastructure.redis.queue import close_queue_clients


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动失败同样释放已取得的连接。"""
    app.state.startup_complete = False
    app.state.startup_components = {}
    try:
        await startup(app)
        yield
    finally:
        app.state.startup_complete = False
        await shutdown_component("queue_clients", close_queue_clients)
        await shutdown_component("postgres", pg_manager.close)
