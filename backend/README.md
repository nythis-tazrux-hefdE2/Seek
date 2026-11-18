# Seek 后端

FastAPI 接收研究 Input，ARQ worker 执行固定 ChatbotAgent，PostgreSQL 保存最终状态和 checkpoint。Redis 负责投递和短期事件，MinIO 保存附件，container runner 执行受限命令。

安装、启动及排障见[部署说明](../docs/deployment.md)，环境变量和可选服务见[配置参考](../docs/configuration.md)。
