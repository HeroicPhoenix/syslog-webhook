# Syslog Webhook Server

一个轻量级、可配置的 **Syslog → Webhook 转发服务**，适合部署在 **NAS / Docker / 内网环境**，用于从设备（如 Synology、交换机、路由器、服务器）接收 Syslog 日志，并根据规则触发告警通知。

---

## ✨ 功能特性

* ✅ 支持 **RFC5424 Syslog**
* ✅ 兼容 **RFC6587（TCP Octet Counting）**
  （Synology / rsyslog / syslog-ng 常见格式）
* ✅ **TCP 方式监听 Syslog**
* ✅ 基于 **正则表达式** 的多规则匹配
* ✅ 命中规则即触发 **Webhook（HTTP POST）**
* ✅ **测试模式（test_mode）**

  * 打印每一条收到的日志
  * 无条件触发测试 webhook，方便排错
* ✅ **不落库**，纯内存处理，性能高、部署简单
* ✅ 适合 **Docker / NAS（群晖）长期运行**

---

## 🏗 架构示意

```text
设备（NAS / 路由 / 交换机）
        |
        |  Syslog (TCP)
        v
+----------------------+
| Syslog Webhook Server|
|  - RFC5424           |
|  - RFC6587           |
|  - Regex Match       |
+----------------------+
        |
        |  HTTP POST
        v
   Webhook 接收端
```

---

## 📂 项目结构

```text
.
├── app/
│   └── syslog_server.py      # 主程序
├── requirements.txt          # Python 依赖
├── Dockerfile                # Docker 镜像构建文件
├── docker-compose.yml        # Docker Compose 示例
└── config/
    └── config.json           # 配置文件（运行时挂载）
```

---

## ⚙️ 配置文件说明（config.json）

配置文件默认从 **`/config/config.json`** 读取（容器内路径）。

### 示例配置

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 12080
  },
  "test_mode": true,
  "test_webhook": {
    "url": "http://192.168.3.99:12082/notify",
    "title": "Syslog 测试消息",
    "url_field": "https://example.com"
  },
  "rules": [
    {
      "name": "link_state_change",
      "regex": "\\blink\\s+(up|down)\\.",
      "webhook": {
        "url": "http://192.168.3.99:12082/notify",
        "title": "设备网络链路状态变化",
        "url_field": ""
      }
    }
  ]
}
```

---

### 配置字段说明

#### `server`

| 字段   | 说明                 |
| ---- | ------------------ |
| host | 监听地址，通常用 `0.0.0.0` |
| port | Syslog TCP 监听端口    |

---

#### `test_mode`

```json
"test_mode": true
```

* `true`：

  * 打印 **每一条原始日志**
  * **无条件触发测试 webhook**
* `false`：

  * 只在命中规则时才触发 webhook

👉 **强烈建议首次部署时开启**

---

#### `test_webhook`

```json
"test_webhook": {
  "url": "http://xxx/notify",
  "title": "Syslog 测试消息",
  "url_field": ""
}
```

仅在 `test_mode = true` 时生效，用于验证：

* Syslog 链路是否正常
* Webhook 是否可达
* Payload 是否符合预期

---

#### `rules`

支持多条规则，**逐条匹配**。

```json
{
  "name": "link_state_change",
  "regex": "\\blink\\s+(up|down)\\.",
  "webhook": {
    "url": "http://xxx/notify",
    "title": "设备网络链路状态变化",
    "url_field": ""
  }
}
```

* `regex`：Python 正则表达式（忽略大小写）
* 示例可匹配：

  * `link up.`
  * `link down.`
* 不依赖接口名（如 LAN 1 / LAN 5）

---

## 📤 Webhook 请求格式

触发 webhook 时发送 **HTTP POST（JSON）**：

```http
POST /notify
Content-Type: application/json
```

```json
{
  "title": "设备网络链路状态变化",
  "msg": "link down.",
  "url": ""
}
```

---

## 🐳 Docker 部署

### Dockerfile

项目已提供完整 Dockerfile，可直接构建镜像。

```dockerfile
FROM crpi-v2fmzydhnzmlpzjc.cn-shanghai.personal.cr.aliyuncs.com/machenkai/python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Shanghai

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    && rm -rf /root/.cache/pip

COPY app /app

VOLUME ["/config", "/logs", "/output"]

EXPOSE 12080

CMD ["python", "syslog_server.py"]
```

---

### docker-compose 示例（NAS / 群晖推荐）

```yaml
services:
  syslog-webhook:
    image: crpi-v2fmzydhnzmlpzjc.cn-shanghai.personal.cr.aliyuncs.com/machenkai/syslog-webhook:latest
    container_name: syslog-webhook
    ports:
      - "12080:12080"
    volumes:
      - /volume1/docker/syslog-webhook/config/config.json:/config/config.json:ro
      - /volume1/docker/syslog-webhook/output:/output
      - /volume1/docker/syslog-webhook/logs:/logs
    restart: always
```

---

## 🧪 调试建议

1. **首次部署**

   * 打开 `test_mode = true`
   * 观察容器日志
   * 确认 webhook 能收到测试消息

2. **验证无误后**

   * 将 `test_mode` 设为 `false`
   * 仅在命中规则时触发告警

---

## 🚀 适用场景

* NAS（群晖）网络链路抖动监控
* 交换机 / 路由器端口 up/down 告警
* 服务器系统日志转通知
* 内网无 ELK / Graylog 的轻量告警方案

---

## 📌 说明

* 本项目 **不做日志存储**
* 专注于 **实时匹配 + 通知**
* 设计目标：**简单、可靠、可控**