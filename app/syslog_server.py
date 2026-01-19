#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RFC5424 Syslog TCP Server (Configurable)
=======================================

功能：
- TCP 监听 RFC5424 syslog（端口来自 JSON 配置）
- 从 JSON 文件读取多条匹配规则
- 每条规则可指定不同 webhook
- 命中规则即触发 webhook
- 不落库，仅内存处理
- 适合 Docker / NAS 生产部署
"""

import socketserver
import logging
import json
import re
import requests
from pathlib import Path
from syslog_rfc5424_parser import SyslogMessage

# =========================
# 配置加载
# =========================

CONFIG_PATH = Path("/config/config.json")


def load_config():
    if not CONFIG_PATH.exists():
        raise RuntimeError(f"配置文件不存在：{CONFIG_PATH}")

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    # 预编译正则，提高性能
    for rule in cfg.get("rules", []):
        rule["compiled_regex"] = re.compile(rule["regex"], re.IGNORECASE)

    return cfg


config = load_config()

SERVER_HOST = config["server"].get("host", "0.0.0.0")
SERVER_PORT = config["server"].get("port", 12080)

RULES = config.get("rules", [])

# =========================
# 日志配置
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger("syslog-server")

# =========================
# TCP Handler
# =========================

class SyslogTCPHandler(socketserver.StreamRequestHandler):
    """
    RFC5424 TCP Syslog Handler
    """

    def handle(self):
        client_ip, client_port = self.client_address
        logger.info(f"连接建立：{client_ip}:{client_port}")

        for raw_line in self.rfile:
            try:
                message = raw_line.decode("utf-8", errors="ignore").strip()
                if not message:
                    continue

                # RFC5424 解析
                syslog = SyslogMessage.parse(message)
                event = syslog.as_dict()

                msg_content = event.get("msg", "")

                logger.info(
                    f"收到日志 | host={event.get('hostname')} "
                    f"app={event.get('appname')} "
                    f"msg={msg_content}"
                )

                self.match_rules(event, msg_content)

            except Exception as e:
                logger.exception(f"日志处理异常：{e}")

        logger.info(f"连接关闭：{client_ip}:{client_port}")

    def match_rules(self, event: dict, msg: str):
        """
        遍历所有规则，逐条匹配
        """
        for rule in RULES:
            if rule["compiled_regex"].search(msg):
                logger.warning(
                    f"命中规则 [{rule['name']}]，触发 webhook"
                )
                self.trigger_webhook(rule, event)

    def trigger_webhook(self, rule: dict, event: dict):
        """
        发送 webhook
        """
        payload = {
            "title": rule["webhook"].get("title", "Syslog 告警"),
            "msg": event.get("msg", ""),
            "url": rule["webhook"].get("url_field", "")
        }

        try:
            resp = requests.post(
                rule["webhook"]["url"],
                json=payload,
                timeout=5
            )

            logger.info(
                f"Webhook 已发送 | rule={rule['name']} "
                f"status={resp.status_code}"
            )

        except Exception as e:
            logger.error(
                f"Webhook 发送失败 | rule={rule['name']} | {e}"
            )

# =========================
# TCP Server
# =========================

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True


# =========================
# 主入口
# =========================

def main():
    logger.info(
        f"Syslog RFC5424 TCP Server 启动，监听 {SERVER_HOST}:{SERVER_PORT}"
    )
    logger.info(f"已加载规则数：{len(RULES)}")

    with ThreadedTCPServer(
        (SERVER_HOST, SERVER_PORT),
        SyslogTCPHandler
    ) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
