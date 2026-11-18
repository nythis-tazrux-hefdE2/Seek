"""显式注册业务和知识 ORM 映射，供 Schema 初始化与测试独立装配。"""

from importlib import import_module

from seek.infrastructure.postgres.base import BusinessBase, KnowledgeBase

MODEL_MODULES = (
    "seek.modules.agents.models.definitions",
    "seek.modules.agents.models.sessions",
    "seek.modules.agents.models.cooperation",
    "seek.modules.agents.models.inputs",
    "seek.modules.agents.models.attachments",
    "seek.modules.agents.models.turns",
    "seek.modules.agents.models.runs",
    "seek.modules.agents.models.sandbox",
    "seek.modules.agents.models.messages",
    "seek.modules.agents.models.feedback",
    "seek.modules.workspace.models",
    "seek.modules.identity.models",
    "seek.modules.extensions.skills.models",
    "seek.modules.extensions.mcp.models",
    "seek.modules.models.tables",
    "seek.modules.system.models",
    "seek.modules.background_jobs.models",
    "seek.modules.schedules.models",
    "seek.modules.knowledge.models",
)


def load_models() -> tuple:
    """加载全部映射并返回两个独立 metadata。"""
    for module in MODEL_MODULES:
        import_module(module)
    return BusinessBase.metadata, KnowledgeBase.metadata
