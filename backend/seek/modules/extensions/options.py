"""本模块拥有的管理员配置定义。"""

from seek.modules.system.services.options import Option
from seek.shared.web_providers import WEB_PROVIDERS

WEB_PROVIDER_OPTIONS = {
    provider.id: Option(
        key=f"{provider.id}_search_opts",
        name=provider.name,
        description="网页搜索与正文抓取凭据。" if provider.supports_fetch else f"{provider.name} 网页搜索凭据。",
        params={
            "provider": {
                "id": provider.id,
                "supports_fetch": provider.supports_fetch,
                "environment": provider.environment,
            },
            "fields": [
                {
                    "key": "api_key",
                    "label": "API Key",
                    "type": "password",
                    "sensitive": True,
                    "environment": provider.environment,
                }
            ],
        },
    )
    for provider in WEB_PROVIDERS
}
