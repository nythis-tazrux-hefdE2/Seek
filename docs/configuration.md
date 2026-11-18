# 配置参考

本页拥有 Seek 的部署变量、模型与网络服务配置说明。完整部署变量以仓库根目录的 `.env.template` 和 `docker-compose.yml` 为准；管理员设置由实际配置 schema 拥有。真实凭据只保存在私有环境或受保护的服务设置中。

## 模型与网页服务

首次启动可在 `.env` 填写 `DEEPSEEK_API_KEY`、`TAVILY_API_KEY`。这两个名称遵循供应商约定，不添加项目品牌前缀。API 与 worker 必须读取同一份实例配置。

| 配置位置 | 操作与生效方式 |
|---|---|
| 设置 → 模型服务 | 启用服务，填写 API Key 或 API Key Env，确认模型列表并测试连接。已有管理员配置不会被内置模板覆盖 |
| 设置 → 基本设置 | 选择已启用、可用的默认对话模型与快速响应模型；不能只填写一个不存在的模型 ID |
| 设置 → 网络搜索 | 配置默认搜索与抓取供应商及其凭据。Tavily 支持搜索和正文抓取；其他供应商以界面实际能力为准 |

模型凭据优先使用数据库中的直接配置，其次使用 `API Key Env` 指定的环境变量。系统选项按数据库、对应环境变量、默认值解析。更新 `.env` 后需重建读取环境的应用容器；数据库中已有直接配置时，应在设置页更新对应字段。模型连接成功只验证该连接，不证明完整研究流程完成。

## 实例、端口与密钥

| 变量或字段 | 默认值 / 用途 |
|---|---|
| `COMPOSE_PROJECT_NAME` | `seek`；容器、网络与镜像的实例命名 |
| `SEEK_STATE_DIR` | `./docker/volumes`；持久化数据根目录 |
| `SEEK_API_PORT` / `SEEK_FRONTEND_PORT` | `35050` / `35173` |
| `SEEK_POSTGRES_PORT` / `SEEK_REDIS_PORT` | `35432` / `36379`；默认绑定 loopback |
| `SEEK_MINIO_API_PORT` / `SEEK_MINIO_CONSOLE_PORT` | `39000` / `39001`；默认绑定 loopback |
| `SEEK_CORS_ORIGINS` / `SEEK_PUBLIC_URL` | 与实际前端入口一致；变更端口或域名时同步调整 |
| `WEB_SEARCH_PROVIDER` | `tavily`；默认搜索服务，可被管理员设置覆盖 |
| `SEEK_INSTANCE_ID` | 初始化生成的实例标识 |
| `SEEK_ENCRYPTION_KEY` | 初始化生成的持久实例密钥；随私有配置备份，勿随意轮换 |
| `JWT_SECRET_KEY` / `API_KEY_DERIVATION_SECRET` | 初始化生成的独立签名/派生密钥，不能复用 |
| 数据库、MinIO、runner 凭据 | 初始化生成；不向研究执行容器暴露管理权限 |

已有实例不要为了修改显示名称直接改数据库、存储根目录、实例标识或密钥。名称不是数据迁移：修改挂载目录可能使原数据不可见，轮换实例密钥需要单独确认受影响的配置。此类变更需要单独的兼容方案和备份。

## 可选服务与生产覆盖

- **附件解析**：普通文本不需要外部 OCR。PDF、图片和其他格式按所选解析器与模型能力处理；需要的凭据或服务未配置时，操作会报告不可用。
- **Langfuse**：`LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`、`LANGFUSE_BASE_URL` 用于可选远端观测；默认不提供凭据。本地 PG 审计、Dashboard 与反馈不依赖远端连接，Trace 入口保持超级管理员权限。
- **生产装配**：`docker-compose.prod.yml` 使用生产前端并收窄 API 绑定；需要 `SANDBOX_CONTAINER_IMAGE_DIGEST` 指定实际执行镜像 digest。域名、HTTPS 与反向代理由部署者提供，本仓库不预设公开地址。

初始化器不会从其他项目复制配置或数据。配置变更后的检查方式见[部署说明](deployment.md)。
