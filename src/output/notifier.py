"""
通知推送模块
================
- Server酱 (微信推送): https://sct.ftqq.com/
- 邮件推送: SMTP
仅在需要操作（非"保持定投"）时发送通知。
"""

import logging
import json
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional

import requests

from config import (
    SERVER_CHAN_KEY, EMAIL_SMTP_HOST, EMAIL_SMTP_PORT,
    EMAIL_USER, EMAIL_PASSWORD, EMAIL_TO, GITHUB_PAGES_URL,
)

logger = logging.getLogger(__name__)


def send_notification(decision_result: Dict, report_url: str = "") -> Dict:
    """
    根据决策结果决定是否推送通知。
    返回 {"sent": bool, "channels": [str, ...], "error": str|None}
    """
    result = {"sent": False, "channels": [], "error": None}

    if not decision_result.get("need_notify"):
        logger.info("Decision is '保持定投', skipping notification")
        return result

    decision = decision_result.get("decision", "未知")
    action = decision_result.get("action", "")
    emoji = decision_result.get("emoji", "")
    total_score = decision_result.get("total_score", 0)

    # 构建消息
    title = f"{emoji} 纳指定投建议: {decision}"
    content = (
        f"## {emoji} {decision}\n\n"
        f"> {action}\n\n"
        f"- **综合评分**: {total_score:.1f} 分\n"
        f"- **日期**: {datetime.now().strftime('%Y-%m-%d')}\n\n"
    )
    if report_url:
        content += f"[📊 查看完整报告]({report_url})\n"

    # 1. Server酱 微信推送
    if SERVER_CHAN_KEY:
        try:
            server_result = _send_server_chan(title, content)
            if server_result:
                result["channels"].append("server_chan")
                logger.info("Server酱 notification sent")
        except Exception as e:
            logger.error(f"Server酱 send failed: {e}")

    # 2. 邮件推送
    if EMAIL_SMTP_HOST and EMAIL_USER and EMAIL_PASSWORD and EMAIL_TO:
        try:
            email_result = _send_email(title, content + f"\n\n完整报告: {report_url}")
            if email_result:
                result["channels"].append("email")
                logger.info("Email notification sent")
        except Exception as e:
            logger.error(f"Email send failed: {e}")

    result["sent"] = len(result["channels"]) > 0
    return result


def _send_server_chan(title: str, content: str) -> bool:
    """
    通过 Server酱 发送微信推送。
    API: https://sctapi.ftqq.com/{SENDKEY}.send
    """
    url = f"https://sctapi.ftqq.com/{SERVER_CHAN_KEY}.send"
    payload = {
        "title": title,
        "desp": content,
    }
    try:
        resp = requests.post(url, data=payload, timeout=10)
        data = resp.json()
        if data.get("code") == 0:
            return True
        logger.warning(f"Server酱 returned: {data}")
        return False
    except Exception as e:
        logger.error(f"Server酱 request failed: {e}")
        return False


def _send_email(subject: str, body: str) -> bool:
    """
    通过 SMTP 发送邮件通知。
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAIL_USER
        msg["To"] = EMAIL_TO

        # Markdown → HTML (简单转换)
        html_body = body
        html_body = html_body.replace("## ", "<h2>").replace("\n\n", "<br><br>")
        html_body = html_body.replace("**", "<b>").replace("**", "</b>")
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False
