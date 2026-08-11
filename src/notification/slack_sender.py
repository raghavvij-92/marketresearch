"""Slack incoming-webhook sender."""

from __future__ import annotations

import logging

import requests

from src.notification.base import BaseSender, chunk_text

logger = logging.getLogger(__name__)

_SLACK_LIMIT = 3500


class SlackSender(BaseSender):
    name = "slack"

    @property
    def configured(self) -> bool:
        return bool(self.config.slack_webhook_url)

    def send(self, text: str, html_body: str = "") -> bool:
        ok = True
        for chunk in chunk_text(text, _SLACK_LIMIT):
            resp = requests.post(
                self.config.slack_webhook_url,
                json={"text": chunk},
                timeout=self.config.request_timeout,
            )
            if resp.status_code != 200:
                logger.error("slack send failed: HTTP %s %s", resp.status_code, resp.text[:200])
                ok = False
        return ok
