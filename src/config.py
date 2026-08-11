"""
Central configuration, loaded from environment variables (and an optional .env file).

Every knob of the pipeline is controlled here so the same code runs locally,
in Docker, and inside GitHub Actions without modification.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is optional
    pass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name, "")
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


def _env_list(name: str, default: str = "") -> List[str]:
    raw = _env(name, default)
    return [item.strip() for item in raw.replace(";", ",").split(",") if item.strip()]


DEFAULT_WATCHLIST = "RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK"


@dataclass
class Config:
    """Runtime configuration for the whole pipeline."""

    # ------------------------------------------------------------------ stocks
    stock_list: List[str] = field(default_factory=list)

    # --------------------------------------------------------------------- LLM
    # Providers are tried in the order below; the first with a key wins unless
    # LLM_PROVIDER pins one explicitly ("gemini" | "openai" | "anthropic").
    llm_provider: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 8192
    llm_timeout: int = 180
    llm_max_retries: int = 3

    # -------------------------------------------------------------------- data
    history_days: int = 400          # calendar days of OHLCV pulled per stock
    enable_nse_direct: bool = True   # hit nseindia.com for delivery %, FII/DII, announcements
    request_timeout: int = 20

    # -------------------------------------------------------------------- news
    enable_news: bool = True
    news_per_stock: int = 8
    news_window_days: int = 7
    tavily_api_key: str = ""
    serpapi_api_key: str = ""

    # ----------------------------------------------------------- notifications
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""
    slack_webhook_url: str = ""
    email_sender: str = ""
    email_password: str = ""
    email_receivers: List[str] = field(default_factory=list)
    email_smtp_server: str = ""
    email_smtp_port: int = 465

    # ------------------------------------------------------------------ output
    output_dir: str = "reports"
    database_path: str = "data/analysis_history.db"
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            stock_list=_env_list("STOCK_LIST", DEFAULT_WATCHLIST),
            llm_provider=_env("LLM_PROVIDER").lower(),
            gemini_api_key=_env("GEMINI_API_KEY"),
            gemini_model=_env("GEMINI_MODEL", "gemini-2.0-flash"),
            openai_api_key=_env("OPENAI_API_KEY"),
            openai_base_url=_env("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            openai_model=_env("OPENAI_MODEL", "gpt-4o-mini"),
            anthropic_api_key=_env("ANTHROPIC_API_KEY"),
            anthropic_model=_env("ANTHROPIC_MODEL", "claude-sonnet-5"),
            llm_temperature=_env_float("LLM_TEMPERATURE", 0.3),
            llm_max_tokens=_env_int("LLM_MAX_TOKENS", 8192),
            llm_timeout=_env_int("LLM_TIMEOUT", 180),
            llm_max_retries=_env_int("LLM_MAX_RETRIES", 3),
            history_days=_env_int("HISTORY_DAYS", 400),
            enable_nse_direct=_env_bool("ENABLE_NSE_DIRECT", True),
            request_timeout=_env_int("REQUEST_TIMEOUT", 20),
            enable_news=_env_bool("ENABLE_NEWS", True),
            news_per_stock=_env_int("NEWS_PER_STOCK", 8),
            news_window_days=_env_int("NEWS_WINDOW_DAYS", 7),
            tavily_api_key=_env("TAVILY_API_KEY"),
            serpapi_api_key=_env("SERPAPI_API_KEY"),
            telegram_bot_token=_env("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=_env("TELEGRAM_CHAT_ID"),
            discord_webhook_url=_env("DISCORD_WEBHOOK_URL"),
            slack_webhook_url=_env("SLACK_WEBHOOK_URL"),
            email_sender=_env("EMAIL_SENDER"),
            email_password=_env("EMAIL_PASSWORD"),
            email_receivers=_env_list("EMAIL_RECEIVERS"),
            email_smtp_server=_env("EMAIL_SMTP_SERVER"),
            email_smtp_port=_env_int("EMAIL_SMTP_PORT", 465),
            output_dir=_env("OUTPUT_DIR", "reports"),
            database_path=_env("DATABASE_PATH", "data/analysis_history.db"),
            log_level=_env("LOG_LEVEL", "INFO").upper(),
        )

    # ------------------------------------------------------------------ helpers
    def resolved_llm_provider(self) -> Optional[str]:
        """Return the provider to use, or None when no key is configured."""
        if self.llm_provider in {"gemini", "openai", "anthropic"}:
            key = {
                "gemini": self.gemini_api_key,
                "openai": self.openai_api_key,
                "anthropic": self.anthropic_api_key,
            }[self.llm_provider]
            return self.llm_provider if key else None
        if self.gemini_api_key:
            return "gemini"
        if self.openai_api_key:
            return "openai"
        if self.anthropic_api_key:
            return "anthropic"
        return None

    def has_any_notifier(self) -> bool:
        return bool(
            (self.telegram_bot_token and self.telegram_chat_id)
            or self.discord_webhook_url
            or self.slack_webhook_url
            or (self.email_sender and self.email_password and self.email_receivers)
        )


_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def reset_config() -> None:
    """Testing hook — force re-read of environment on next get_config()."""
    global _config
    _config = None
