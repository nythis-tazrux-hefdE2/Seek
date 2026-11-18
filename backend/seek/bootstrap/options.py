"""启动时汇总各域配置并同步持久定义；汇总属于组合根，不进入 system 模块。"""

from sqlalchemy.ext.asyncio import AsyncSession

from seek.modules.documents.options import DOCUMENT_OPTIONS
from seek.modules.extensions.options import WEB_PROVIDER_OPTIONS
from seek.modules.system.options import system_options
from seek.modules.system.repositories.options import sync_option_definitions
from seek.modules.system.services.options import Option


def get_option_definitions() -> dict[str, Option]:
    """显式汇总各模块配置定义，系统管理机制不拥有领域定义。"""
    return {option.key: option for option in (*DOCUMENT_OPTIONS, *WEB_PROVIDER_OPTIONS.values(), system_options)}


async def ensure_options_in_db(db: AsyncSession) -> None:
    """保留管理员值，幂等更新代码拥有的定义。"""
    await sync_option_definitions(db, get_option_definitions())
