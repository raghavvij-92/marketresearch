"""Discord webhook sender (chunked to the 2000-char message limit)."""

from __future__ import annotations

import logging

import requests

from src.notification.base import BaseSender, chunk_text

logger = logging.getLogger(__name__)

_DISCORD_LIMIT = 1900


class DiscordSender(BaseSender):
    name = "discord"

    @property
    def configured(self) -> bool:
        return bool(self.config.discord_webhook_url)

    def send(self, text: str, html_body: str = "") -> bool:
        ok = True
        for chunk in chunk_text(text, _DISCORD_LIMIT):
            resp = requests.post(
                self.config.discord_webhook_url,
                json={"content": chunk},
                timeout=self.config.request_timeout,
            )
            if resp.status_code not in (200, 204):
                logger.error("discord send failed: HTTP %s %s", resp.status_code, resp.text[:200])
                ok = False
        return ok
