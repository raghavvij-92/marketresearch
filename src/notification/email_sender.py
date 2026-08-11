"""SMTP email sender (SSL). Sends the full digest as HTML with a text fallback."""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.notification.base import BaseSender

logger = logging.getLogger(__name__)

# Common providers so users only need EMAIL_SENDER + EMAIL_PASSWORD.
_SMTP_BY_DOMAIN = {
    "gmail.com": ("smtp.gmail.com", 465),
    "outlook.com": ("smtp-mail.outlook.com", 587),
    "hotmail.com": ("smtp-mail.outlook.com", 587),
    "yahoo.com": ("smtp.mail.yahoo.com", 465),
    "yahoo.in": ("smtp.mail.yahoo.com", 465),
    "rediffmail.com": ("smtp.rediffmail.com", 465),
    "zoho.com": ("smtp.zoho.com", 465),
    "zoho.in": ("smtp.zoho.in", 465),
}


class EmailSender(BaseSender):
    name = "email"

    @property
    def configured(self) -> bool:
        return bool(
            self.config.email_sender
            and self.config.email_password
            and self.config.email_receivers
        )

    def _smtp_settings(self) -> tuple[str, int]:
        if self.config.email_smtp_server:
            return self.config.email_smtp_server, self.config.email_smtp_port
        domain = self.config.email_sender.rsplit("@", 1)[-1].lower()
        return _SMTP_BY_DOMAIN.get(domain, (f"smtp.{domain}", 465))

    def send(self, text: str, html_body: str = "") -> bool:
        server, port = self._smtp_settings()
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🇮🇳 India Stock Research — {datetime.now().strftime('%Y-%m-%d')}"
        msg["From"] = self.config.email_sender
        msg["To"] = ", ".join(self.config.email_receivers)
        msg.attach(MIMEText(text, "plain", "utf-8"))
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))
        try:
            if port == 465:
                with smtplib.SMTP_SSL(server, port, timeout=30) as smtp:
                    smtp.login(self.config.email_sender, self.config.email_password)
                    smtp.sendmail(
                        self.config.email_sender, self.config.email_receivers, msg.as_string()
                    )
            else:
                with smtplib.SMTP(server, port, timeout=30) as smtp:
                    smtp.starttls()
                    smtp.login(self.config.email_sender, self.config.email_password)
                    smtp.sendmail(
                        self.config.email_sender, self.config.email_receivers, msg.as_string()
                    )
            return True
        except Exception as exc:
            logger.error("email send failed via %s:%s — %s", server, port, exc)
            return False
