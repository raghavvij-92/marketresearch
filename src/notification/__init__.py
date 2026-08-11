"""Multi-channel notification dispatch (Telegram / Discord / Slack / Email)."""

from __future__ import annotations

import logging
from typing import List

from src.config import Config
from src.notification.base import BaseSender
from src.notification.discord_sender import DiscordSender
from src.notification.email_sender import EmailSender
from src.notification.slack_sender import SlackSender
from src.notification.telegram_sender import TelegramSender

logger = logging.getLogger(__name__)


def build_senders(config: Config) -> List[BaseSender]:
    senders: List[BaseSender] = []
    for cls in (TelegramSender, DiscordSender, SlackSender, EmailSender):
        sender = cls(config)
        if sender.configured:
            senders.append(sender)
    return senders


def send_all(config: Config, text: str, html_body: str = "") -> List[str]:
    """Send to every configured channel; returns names of channels that succeeded."""
    delivered: List[str] = []
    for sender in build_senders(config):
        try:
            if sender.send(text, html_body=html_body):
                delivered.append(sender.name)
        except Exception as exc:
            logger.error("%s notification failed: %s", sender.name, exc)
    return delivered
