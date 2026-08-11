"""Common sender interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from src.config import Config


class BaseSender(ABC):
    name = "base"

    def __init__(self, config: Config):
        self.config = config

    @property
    @abstractmethod
    def configured(self) -> bool:
        """Whether the credentials for this channel are present."""

    @abstractmethod
    def send(self, text: str, html_body: str = "") -> bool:
        """Deliver the message; return True on success."""


def chunk_text(text: str, limit: int) -> List[str]:
    """Split on line boundaries so no chunk exceeds the given character limit."""
    if len(text) <= limit:
        return [text]
    chunks: List[str] = []
    current: List[str] = []
    size = 0
    for line in text.split("\n"):
        # A single pathological line longer than the limit gets hard-split.
        while len(line) > limit:
            if current:
                chunks.append("\n".join(current))
                current, size = [], 0
            chunks.append(line[:limit])
            line = line[limit:]
        if size + len(line) + 1 > limit and current:
            chunks.append("\n".join(current))
            current, size = [], 0
        current.append(line)
        size += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks
