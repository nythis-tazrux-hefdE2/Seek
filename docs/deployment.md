# 部署与运行

本文面向自行部署 Seek 的使用者，说明启动、持久化和故障处理。需要 Python 3、Docker Engine、Docker Compose v2，以及模型和搜索服务凭据。Linux/WSL 是本地验证环境；依赖、镜像和外部服务需要可用网络。

## 首次启动

在包含 `docker-compose.yml` 的仓库根目录执行：

```bash
bash scripts/init.sh
```

脚本生成权限为 0600 的私有 `.env`，为数据库、对象存储、签名、加密和 runner 生成独立密钥。填写 `DEEPSEEK_API_KEY`、`TAVILY_API_KEY`；字段含义和可选项见[配置参考](configuration.md)。

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
curl --fail http://localhost:35050/api/system/ready
```

readiness 返回 `status: ready` 后，打开 `http://localhost:35173` 创建首位管理员并登录。在系统设置启用模型服务、确认可用模型与默认项，检查搜索和抓取设置，再提交一个[研究任务](research.md)。已有数据库有账号时继续使用原账号，初始化不会另建管理员。Windows 初始化脚本为 `scripts/init.ps1`，需要可调用的 Python 3 和 Docker Compose。

## 初始化与持久化

默认 Compose 装配前端、API、worker、PostgreSQL、Redis、MinIO、runner、执行镜像与初始化任务。`storage-init` 准备目录，`app-init` 校验并初始化数据库、PostgreSQL checkpoint、固定研究配置和内置 Skill。

数据默认保存到仓库的 `docker/volumes`。工作目录、Skill 来源/投影、数据库和对象存储均属于本实例。备份需要同时保留 PostgreSQL、文件/对象数据及对应私有配置，尤其是加密和签名密钥。运行目录和备份不要加入 Git。

已有 `.env` 的非空值保持不变，空项或缺失字段会补齐。完整配置重复运行初始化器保持原字节。需要重跑应用初始化时：

```bash
docker compose run --rm app-init
```

先修复报错原因再重跑，不以重置数据库或删除存储替代恢复。更新部署时保留同一实例的数据目录与私有配置，不通过修改存储目录或重置数据库处理启动错误。

## 日常运行与排障

- 进程存活检查为 `/api/system/health`；接流量条件由 `/api/system/ready` 判断。它们不替代真实研究验证。
- 用 `docker compose logs api worker sandbox-runner` 在本地排查启动、投递或执行错误，公开日志前清除业务内容与敏感信息。
- 用 `docker compose stop` 停止服务并保留数据；用 `docker compose up -d` 恢复。正常更新使用 `docker compose up -d --build`，更新前先备份数据和私有配置，并核对所需迁移。
- 研究不可用时分别确认模型启用/连接、默认模型、搜索凭据、worker 和 runner，不能仅凭首页可打开判断研究可用。

默认开发装配会挂载源码。公网部署需使用生产覆盖文件、固定执行镜像 digest，并配置入口代理、HTTPS、访问范围与备份；不要直接把开发端口当作生产入口。生产覆盖的必要参数见[配置参考](configuration.md)。确认 `SANDBOX_CONTAINER_IMAGE_DIGEST` 是实际执行镜像的有效 digest 后运行：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

登录页链接的两份协议为部署模板。提供公开服务前，部署者应按实际业务与数据处理方式编辑模板，填写组织、产品、生效日期和联系方式。
