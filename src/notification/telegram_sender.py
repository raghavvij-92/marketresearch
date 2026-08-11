"""Telegram bot sender (plain text, chunked to the 4096-char API limit)."""

from __future__ import annotations

import logging

import requests

from src.notification.base import BaseSender, chunk_text

logger = logging.getLogger(__name__)

_TELEGRAM_LIMIT = 4000  # a little under the hard 4096 cap


class TelegramSender(BaseSender):
    name = "telegram"

    @property
    def configured(self) -> bool:
        return bool(self.config.telegram_bot_token and self.config.telegram_chat_id)

    def send(self, text: str, html_body: str = "") -> bool:
        url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
        ok = True
        for chunk in chunk_text(text, _TELEGRAM_LIMIT):
            resp = requests.post(
                url,
                json={
                    "chat_id": self.config.telegram_chat_id,
                    "text": chunk,
                    "disable_web_page_preview": True,
                },
                timeout=self.config.request_timeout,
            )
            if resp.status_code != 200:
                logger.error("telegram send failed: HTTP %s %s", resp.status_code, resp.text[:200])
                ok = False
        return ok
