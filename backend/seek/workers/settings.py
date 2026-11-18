"""ARQ worker 的任务注册、并发配置与生命周期回调。"""

from __future__ import annotations

from arq.worker import func

from seek.bootstrap.worker import shutdown, startup
from seek.infrastructure.redis import get_arq_redis_settings
from seek.infrastructure.runtime_settings import get_int_env
from seek.infrastructure.worker_health import WORKER_HEALTH_INTERVAL_SECONDS, WORKER_HEALTH_KEY
from seek.modules.agents.services.runner import MAX_RUN_TRIES, RUN_TIMEOUT_SECONDS, process_agent_run


def worker_max_jobs() -> int:
    """读取单个 ARQ worker 的并发任务上限。"""
    return get_int_env("ARQ_MAX_JOBS", 10)


class WorkerSettings:
    """为 ARQ 提供 Seek 任务、并发和生命周期配置。"""

    functions = [
        func(process_agent_run, timeout=RUN_TIMEOUT_SECONDS + 30, keep_result=0),
    ]
    cron_jobs = []
    max_jobs = worker_max_jobs()
    # 交互请求避免继承 ARQ 默认的 500ms 空闲轮询等待。
    poll_delay = 0.05
    max_tries = MAX_RUN_TRIES
    retry_jobs = True
    # Agent 的业务时限由 runner 拥有，ARQ 额外保留清理与终态提交时间。
    job_timeout = RUN_TIMEOUT_SECONDS + 30
    keep_result = 60
    health_check_interval = WORKER_HEALTH_INTERVAL_SECONDS
    health_check_key = WORKER_HEALTH_KEY
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = get_arq_redis_settings()
