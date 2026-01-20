#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RFC5424 / RFC6587 Syslog TCP Server (Configurable)
=================================================

功能：
- TCP 监听 Syslog（RFC5424）
- 兼容 RFC6587 Octet Counting（Synology / rsyslog 常见）
- 从 JSON 文件读取多条正则匹配规则
- 命中规则即触发 webhook
- 测试模式下：无脑触发测试 webhook
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

    # 预编译正则
    for rule in cfg.get("rules", []):
        rule["compiled_regex"] = re.compile(
            rule["regex"],
            re.IGNORECASE
        )

    return cfg


config = load_config()

SERVER_HOST = config.get("server", {}).get("host", "0.0.0.0")
SERVER_PORT = config.get("server", {}).get("port", 12080)

RULES = config.get("rules", [])

TEST_MODE = config.get("test_mode", False)
TEST_WEBHOOK = config.get("test_webhook")

# =========================
# 日志配置
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger("syslog-server")

# =========================
# 工具函数
# =========================

def strip_octet_counting(msg: str) -> str:
    """
    去除 RFC6587 TCP Syslog 的 Octet Counting 前缀
    """
    if not msg:
        return msg

    if msg[0].isdigit():
        parts = msg.split(" ", 1)
        if len(parts) == 2 and parts[0].isdigit():
            return parts[1]

    return msg

# =========================
# TCP Handler
# =========================

class SyslogTCPHandler(socketserver.StreamRequestHandler):

    def handle(self):
        client_ip, client_port = self.client_address
        logger.info(f"连接建立：{client_ip}:{client_port}")

        for raw_line in self.rfile:
            raw_message = None
            try:
                raw_message = raw_line.decode(
                    "utf-8",
                    errors="ignore"
                ).strip()

                if not raw_message:
                    continue

                # 测试模式：打印原始日志
                if TEST_MODE:
                    logger.info(f"[TEST_MODE] 原始日志：{raw_message}")

                message = strip_octet_counting(raw_message)

                # RFC5424 解析
                syslog = SyslogMessage.parse(message)
                event = syslog.as_dict()

                msg_content = event.get("msg", "")

                logger.info(
                    f"收到日志 | host={event.get('hostname')} "
                    f"app={event.get('appname')} "
                    f"msg={msg_content}"
                )

                # =========================
                # 测试模式：无条件触发测试 webhook
                # =========================
                if TEST_MODE and TEST_WEBHOOK:
                    self.trigger_test_webhook(event)

                # 正式规则匹配
                self.match_rules(event, msg_content)

            except Exception as e:
                logger.error("日志处理异常（已忽略，服务继续运行）")
                if raw_message:
                    logger.error(f"异常日志原文：{raw_message}")
                logger.exception(e)

        logger.info(f"连接关闭：{client_ip}:{client_port}")

    def match_rules(self, event: dict, msg: str):
        for rule in RULES:
            if rule["compiled_regex"].search(msg):
                logger.warning(
                    f"命中规则 [{rule['name']}]，触发 webhook"
                )
                self.trigger_rule_webhook(rule, event)

    def trigger_rule_webhook(self, rule: dict, event: dict):
        payload = {
            "title": rule.get("webhook", {}).get(
                "title", "Syslog 告警"
            ),
            "msg": event.get("msg", ""),
            "url": rule.get("webhook", {}).get(
                "url_field", ""
            )
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

    def trigger_test_webhook(self, event: dict):
        payload = {
            "title": TEST_WEBHOOK.get(
                "title", "Syslog 测试"
            ),
            "msg": event.get("msg", ""),
            "url": TEST_WEBHOOK.get(
                "url_field", ""
            )
        }

        try:
            resp = requests.post(
                TEST_WEBHOOK["url"],
                json=payload,
                timeout=5
            )
            logger.info(
                f"[TEST_MODE] 测试 webhook 已发送 "
                f"status={resp.status_code}"
            )
        except Exception as e:
            logger.error(
                f"[TEST_MODE] 测试 webhook 发送失败：{e}"
            )

# =========================
# TCP Server
# =========================

class ThreadedTCPServer(
    socketserver.ThreadingMixIn,
    socketserver.TCPServer
):
    allow_reuse_address = True
    daemon_threads = True

# =========================
# 主入口
# =========================

def main():
    logger.info(
        f"Syslog TCP Server 启动，监听 {SERVER_HOST}:{SERVER_PORT}"
    )
    logger.info(f"已加载规则数：{len(RULES)}")
    logger.info(f"测试模式：{'开启' if TEST_MODE else '关闭'}")
    logger.info(f"配置文件路径：{CONFIG_PATH}")

    if TEST_MODE and not TEST_WEBHOOK:
        logger.warning(
            "测试模式已开启，但未配置 test_webhook"
        )

    with ThreadedTCPServer(
        (SERVER_HOST, SERVER_PORT),
        SyslogTCPHandler
    ) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
