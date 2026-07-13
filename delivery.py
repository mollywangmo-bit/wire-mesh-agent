"""
丝网行业研究 Agent - 投递模块

支持多渠道投递：
1. 邮件（SMTP，Word 附件）
2. 飞书机器人（Webhook，交互式卡片）
3. 企业微信机器人（Webhook，markdown）
"""
import socket
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.header import Header
from email import encoders
from datetime import datetime
from pathlib import Path
import time

import httpx

from config import Config


SMTP_TIMEOUT = 30
SMTP_RETRIES = 3


def _valid_file(path: str | Path | None) -> bool:
    """附件必须真实存在且非空，避免日志/邮件误报。"""
    if not path:
        return False
    p = Path(path)
    return p.exists() and p.is_file() and p.stat().st_size > 0


class Delivery:
    """报告投递器"""

    def __init__(self, config: Config):
        self.config = config
        self.client = httpx.Client(timeout=20.0)

    def send_email(self, report: str, docx_path: str | None = None,
                   pdf_path: str | None = None,
                   html_path: str | None = None, prefix: str = "周报") -> bool:
        """通过邮件发送报告（含 Word/PDF/HTML 附件），内置重试"""
        cfg = self.config
        if not all([cfg.smtp_server, cfg.smtp_user, cfg.smtp_password, cfg.email_to]):
            print("  [邮件] 配置不完整，跳过")
            return False

        date_str = datetime.now().strftime("%Y-%m-%d")
        subject = f"丝网行业{prefix}｜{date_str}"

        msg = MIMEMultipart()
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = cfg.email_from or cfg.smtp_user
        msg["To"] = cfg.email_to

        # 正文
        body = (
            f"丝网行业{prefix}已生成，请查看附件。\n\n"
            f"- Word：适合编辑和二次加工\n"
            f"- PDF：适合打印和归档\n"
            f"- HTML：适合浏览器可视化阅读\n\n"
            f"正文预览：\n{report[:1200]}"
        )
        if len(report) > 1200:
            body += "\n\n……完整内容请查看附件。"
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Word 附件
        if _valid_file(docx_path):
            with open(docx_path, "rb") as f:
                attachment = MIMEBase("application", "vnd.openxmlformats-officedocument.wordprocessingml.document")
                attachment.set_payload(f.read())
                encoders.encode_base64(attachment)
                attachment.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=f"丝网行业{prefix}_{date_str}.docx",
                )
                msg.attach(attachment)

        # PDF 附件
        if _valid_file(pdf_path):
            with open(pdf_path, "rb") as f:
                attachment = MIMEBase("application", "pdf")
                attachment.set_payload(f.read())
                encoders.encode_base64(attachment)
                attachment.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=f"丝网行业{prefix}_{date_str}.pdf",
                )
                msg.attach(attachment)

        # HTML 附件
        if _valid_file(html_path):
            with open(html_path, "rb") as f:
                html_att = MIMEBase("text", "html")
                html_att.set_payload(f.read())
                encoders.encode_base64(html_att)
                html_att.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=f"丝网行业{prefix}_{date_str}.html",
                )
                msg.attach(html_att)

        last_err = None
        for attempt in range(1, SMTP_RETRIES + 1):
            try:
                socket.setdefaulttimeout(SMTP_TIMEOUT)
                with smtplib.SMTP(cfg.smtp_server, cfg.smtp_port, timeout=SMTP_TIMEOUT) as server:
                    server.starttls()
                    server.login(cfg.smtp_user, cfg.smtp_password)
                    server.send_message(msg)
                attachments = []
                if _valid_file(docx_path):
                    attachments.append("Word")
                if _valid_file(pdf_path):
                    attachments.append("PDF")
                if _valid_file(html_path):
                    attachments.append("HTML")
                suffix = f" (含{' + '.join(attachments)}附件)" if attachments else ""
                print(f"  [邮件] ✓ 已发送至 {cfg.email_to}{suffix}")
                return True
            except Exception as e:
                last_err = e
                if attempt < SMTP_RETRIES:
                    wait = attempt * 5
                    print(f"  [邮件] 第{attempt}次失败 ({e})，{wait}s 后重试...")
                    time.sleep(wait)

        print(f"  [邮件] ✗ 发送失败 ({SMTP_RETRIES}次): {last_err}")
        return False

    def send_feishu(self, report: str, html_path: str | None = None,
                    prefix: str = "周报") -> bool:
        """通过飞书机器人发送（交互式卡片，支持长内容）"""
        if not self.config.feishu_webhook_url:
            print("  [飞书] 未配置 webhook，跳过")
            return False

        date_str = datetime.now().strftime("%Y-%m-%d")
        sections = self._split_report_sections(report)

        # 构建飞书交互式卡片
        elements = []
        for title, body in sections:
            md_content = f"**{title}**\n{body.strip()}"
            elements.append({"tag": "markdown", "content": md_content})

        # HTML 报告提示（放在最后一张卡片末尾）
        if html_path and Path(html_path).exists():
            elements.append({
                "tag": "note",
                "elements": [
                    {"tag": "plain_text", "content": f"🌐 HTML 可视化报告已生成（{Path(html_path).name}），已随邮件发送。"}
                ],
            })

        MAX_ELEMENTS = 25  # 单卡片最大元素数
        MAX_BODY_CHARS = 18000  # 安全限制

        # 如果内容过多，分批发送
        batches = []
        current_batch = []
        current_chars = 0

        for elem in elements:
            text_len = len(str(elem))
            if current_chars + text_len > MAX_BODY_CHARS or len(current_batch) >= MAX_ELEMENTS:
                if current_batch:
                    batches.append(current_batch)
                current_batch = [elem]
                current_chars = text_len
            else:
                current_batch.append(elem)
                current_chars += text_len

        if current_batch:
            batches.append(current_batch)

        for i, batch in enumerate(batches):
            suffix = f" ({i+1}/{len(batches)})" if len(batches) > 1 else ""
            card = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": f"丝网行业{prefix}｜{date_str}{suffix}",
                        },
                        "template": "blue",
                    },
                    "elements": batch,
                },
            }

            try:
                resp = self.client.post(
                    self.config.feishu_webhook_url,
                    json=card,
                )
                resp.raise_for_status()
                result = resp.json()
                if result.get("code") == 0:
                    print(f"  [飞书] ✓ 卡片 {i+1}/{len(batches)} 已发送")
                else:
                    print(f"  [飞书] ✗ 卡片 {i+1} 发送失败: {result}")
                    return False
            except Exception as e:
                print(f"  [飞书] ✗ 卡片 {i+1} 发送失败: {e}")
                return False

        return True

    def _split_report_sections(self, report: str) -> list[tuple[str, str]]:
        """将报告按 ## 标题分割成 (标题, 内容) 段落"""
        lines = report.strip().split("\n")
        sections = []
        current_title = "概要"
        current_body = []

        for line in lines:
            if line.startswith("## "):
                if current_body:
                    sections.append((current_title, "\n".join(current_body)))
                current_title = line.replace("## ", "").strip()
                current_body = []
            elif line.startswith("# "):
                # 主标题忽略
                continue
            else:
                # 清洗 markdown 链接为纯文本（飞书卡片也支持链接，但保留格式）
                current_body.append(line)

        if current_body:
            sections.append((current_title, "\n".join(current_body)))

        return sections

    def send_wecom(self, report: str, prefix: str = "周报") -> bool:
        """通过企业微信机器人发送"""
        if not self.config.wecom_webhook_url:
            print("  [企微] 未配置 webhook，跳过")
            return False

        content = report[:4000]
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"# 丝网行业{prefix}｜{datetime.now().strftime('%Y-%m-%d')}\n\n{content}",
            },
        }

        try:
            resp = self.client.post(
                self.config.wecom_webhook_url,
                json=payload,
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("errcode") == 0:
                print("  [企微] ✓ 已发送")
                return True
            else:
                print(f"  [企微] ✗ 发送失败: {result}")
                return False
        except Exception as e:
            print(f"  [企微] ✗ 发送失败: {e}")
            return False

    def deliver_all(self, report: str, docx_path: str | None = None,
                    pdf_path: str | None = None,
                    html_path: str | None = None, prefix: str = "周报"):
        """向所有已配置的渠道投递报告"""
        print(f"\n  === 投递{prefix} ===")
        results = [
            ("邮件", self.send_email(report, docx_path, pdf_path, html_path, prefix=prefix)),
            ("飞书", self.send_feishu(report, html_path, prefix=prefix)),
            ("企微", self.send_wecom(report, prefix=prefix)),
        ]

        success = sum(1 for _, ok in results if ok)
        for name, ok in results:
            icon = "✓" if ok else "—"
            print(f"    {icon} {name}")
        print(f"  投递完成: {success}/{len(results)} 个渠道成功")
        return success > 0


if __name__ == "__main__":
    from config import load_config
    cfg = load_config()
    d = Delivery(cfg)
    d.deliver_all("测试报告：这是一个测试消息。")
