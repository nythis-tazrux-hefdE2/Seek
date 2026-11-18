# 使用轻量级Python基础镜像
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.6 /uv /uvx /bin/

# 设置工作目录
WORKDIR /app

# 环境变量设置
ENV TZ=Asia/Shanghai \
    UV_PROJECT_ENVIRONMENT="/usr/local" \
    UV_COMPILE_BYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# 设置代理和时区，更换镜像源，安装系统依赖 - 合并为一个RUN减少层数
RUN set -ex \
    # (A) 设置时区
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    # (B) 替换清华源 (针对 Debian Bookworm 的新版格式)
    && sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    # (C) 安装必要的系统库
    && apt-get update \
    && apt-get install -y --no-install-recommends --fix-missing \
        curl \
        ffmpeg \
        fonts-liberation \
        fonts-noto-cjk \
        git \
        libpq5 \
        libsm6 \
        libxext6 \
        libreoffice-calc-nogui \
        libreoffice-impress-nogui \
        libreoffice-writer-nogui \
    # (D) 清理垃圾，减小体积
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 复制项目配置文件
COPY --chown=0:0 --chmod=0644 backend/pyproject.toml /app/pyproject.toml
COPY --chown=0:0 --chmod=0644 backend/.python-version /app/.python-version
COPY --chown=0:0 --chmod=0644 backend/uv.lock /app/uv.lock

# 安装唯一的后端 Python 项目。
COPY --chown=0:0 --chmod=0644 backend/README.md /app/README.md
COPY --chown=0:0 --chmod=0644 backend/MANIFEST.in /app/MANIFEST.in
COPY --chown=0:0 backend/seek /app/seek
# 构建输入可来自 600/700 checkout，镜像内源码只读权限不依赖宿主模式。
RUN find /app/seek -type d -exec chmod 0755 {} + \
    && find /app/seek -type f -exec chmod 0644 {} +

# 如果网络还是不好，可以在后面添加 --index-url https://pypi.tuna.tsinghua.edu.cn/simple
RUN uv sync --no-cache --group test --group dev --frozen

COPY --chown=0:0 --chmod=0755 docker/api-entrypoint.sh /usr/local/bin/seek-entrypoint

RUN groupadd --gid 1000 seek \
    && useradd --uid 1000 --gid 1000 --create-home seek \
    && mkdir -p /app/runtime /home/seek/.cache/rapidocr/models \
    && chown -R 1000:1000 /app/runtime /home/seek

ENV HOME=/home/seek \
    RAPIDOCR_MODEL_DIR=/home/seek/.cache/rapidocr/models

USER 1000:1000

ENTRYPOINT ["/usr/local/bin/seek-entrypoint"]
