FROM crpi-v2fmzydhnzmlpzjc.cn-shanghai.personal.cr.aliyuncs.com/machenkai/python:3.10-slim

# =========================
# 环境变量
# =========================
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Shanghai

# =========================
# 基础依赖（证书 + 时区）
# =========================
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# =========================
# 工作目录
# =========================
WORKDIR /app

# =========================
# Python 依赖
# =========================
COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    && rm -rf /root/.cache/pip

# =========================
# 项目代码
# =========================
COPY app /app

# =========================
# 约定挂载点
# =========================
# /config : config.json（只读挂载）
# /logs   : 预留日志目录
# /output : 预留输出目录
VOLUME ["/config", "/logs", "/output"]

# =========================
# 暴露 Syslog TCP 端口
# =========================
EXPOSE 12080

# =========================
# 启动 Syslog 服务
# =========================
CMD ["python", "syslog_server.py"]
