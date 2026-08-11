"""
News and sentiment inputs.

Free by default:
* Google News RSS, queried per stock ("<company> NSE stock") — surprisingly
  good coverage of Indian corporate news across ET, Moneycontrol, Mint, etc.
* Market-wide RSS feeds from the major Indian financial dailies.

Optional (API key): Tavily and SerpAPI searches for higher-quality retrieval.
All sources are best-effort; failures return empty lists.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import quote_plus

import requests

from src.config import Config
from src.data_provider.base import StockData

logger = logging.getLogger(__name__)

MARKET_FEEDS = [
    ("Economic Times Markets", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("Moneycontrol Markets", "https://www.moneycontrol.com/rss/marketreports.xml"),
    ("LiveMint Markets", "https://www.livemint.com/rss/markets"),
    ("Business Standard Markets", "https://www.business-standard.com/rss/markets-106.rss"),
]

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; IndiaStockResearcher/1.0)"}


@dataclass
class NewsItem:
    title: str
    source: str = ""
    published: str = ""
    url: str = ""
    snippet: str = ""

    def to_prompt_line(self) -> str:
        date = f" [{self.published}]" if self.published else ""
        src = f" — {self.source}" if self.source else ""
        line = f"- {self.title}{src}{date}"
        if self.snippet:
            line += f"\n  {self.snippet[:200]}"
        return line


def _parse_feed(url: str, timeout: int) -> list:
    """Fetch + parse one RSS feed; empty list on any failure."""
    try:
        import feedparser

        resp = requests.get(url, headers=_HEADERS, timeout=timeout)
        if resp.status_code != 200:
            return []
        feed = feedparser.parse(resp.content)
        return list(feed.entries or [])
    except Exception as exc:
        logger.warning("RSS fetch failed for %s: %s", url, exc)
        return []


def _entry_datetime(entry) -> Optional[datetime]:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime.fromtimestamp(time.mktime(parsed))
            except (ValueError, OverflowError):
                continue
    return None


def fetch_stock_news(stock: StockData, config: Config) -> List[NewsItem]:
    """Per-stock news, newest first, within the configured window."""
    if not config.enable_news:
        return []

    items: List[NewsItem] = []
    if config.tavily_api_key:
        items.extend(_tavily_search(stock, config))
    if config.serpapi_api_key and len(items) < config.news_per_stock:
        items.extend(_serpapi_search(stock, config))
    if len(items) < config.news_per_stock:
        items.extend(_google_news(stock, config))

    # De-duplicate by lower-cased title, cap at configured count.
    seen: set = set()
    unique: List[NewsItem] = []
    for item in items:
        key = item.title.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
        if len(unique) >= config.news_per_stock:
            break
    return unique


def _google_news(stock: StockData, config: Config) -> List[NewsItem]:
    # Prefer the full company name — bare symbols like "RELIANCE" also match
    # unrelated listings (Reliance Infra, Reliance Power, ...).
    name = stock.fundamentals.long_name or f"{stock.symbol.symbol} share"
    query = quote_plus(f'"{name}" NSE stock')
    url = (
        f"https://news.google.com/rss/search?q={query}+when:{config.news_window_days}d"
        "&hl=en-IN&gl=IN&ceid=IN:en"
    )
    cutoff = datetime.now() - timedelta(days=config.news_window_days)
    items: List[NewsItem] = []
    for entry in _parse_feed(url, config.request_timeout)[: config.news_per_stock * 2]:
        published = _entry_datetime(entry)
        if published and published < cutoff:
            continue
        source = ""
        src_obj = getattr(entry, "source", None)
        if src_obj is not None:
            source = getattr(src_obj, "title", "") or ""
        items.append(
            NewsItem(
                title=getattr(entry, "title", "").strip(),
                source=source or "Google News",
                published=published.strftime("%Y-%m-%d") if published else "",
                url=getattr(entry, "link", ""),
            )
        )
    return items


def _tavily_search(stock: StockData, config: Config) -> List[NewsItem]:
    name = stock.fundamentals.long_name or stock.symbol.symbol
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": config.tavily_api_key,
                "query": f"{name} NSE stock news",
                "topic": "news",
                "days": config.news_window_days,
                "max_results": config.news_per_stock,
            },
            timeout=config.request_timeout,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except Exception as exc:
        logger.warning("Tavily search failed for %s: %s", stock.symbol.symbol, exc)
        return []
    return [
        NewsItem(
            title=r.get("title", ""),
            source="Tavily",
            published=(r.get("published_date") or "")[:10],
            url=r.get("url", ""),
            snippet=(r.get("content") or "")[:300],
        )
        for r in results
        if r.get("title")
    ]


def _serpapi_search(stock: StockData, config: Config) -> List[NewsItem]:
    name = stock.fundamentals.long_name or stock.symbol.symbol
    try:
        resp = requests.get(
            "https://serpapi.com/search",
            params={
                "engine": "google_news",
                "q": f"{name} NSE stock",
                "gl": "in",
                "hl": "en",
                "api_key": config.serpapi_api_key,
            },
            timeout=config.request_timeout,
        )
        resp.raise_for_status()
        results = resp.json().get("news_results", [])
    except Exception as exc:
        logger.warning("SerpAPI search failed for %s: %s", stock.symbol.symbol, exc)
        return []
    return [
        NewsItem(
            title=r.get("title", ""),
            source=(r.get("source") or {}).get("name", "SerpAPI")
            if isinstance(r.get("source"), dict)
            else str(r.get("source") or "SerpAPI"),
            published=(r.get("date") or "")[:10],
            url=r.get("link", ""),
            snippet=(r.get("snippet") or "")[:300],
        )
        for r in results
        if r.get("title")
    ]


def fetch_market_headlines(config: Config, limit: int = 10) -> List[NewsItem]:
    """Top market-wide headlines across the Indian financial press."""
    if not config.enable_news:
        return []
    items: List[NewsItem] = []
    per_feed = max(2, limit // len(MARKET_FEEDS))
    for source, url in MARKET_FEEDS:
        for entry in _parse_feed(url, config.request_timeout)[:per_feed]:
            published = _entry_datetime(entry)
            items.append(
                NewsItem(
                    title=getattr(entry, "title", "").strip(),
                    source=source,
                    published=published.strftime("%Y-%m-%d") if published else "",
                    url=getattr(entry, "link", ""),
                )
            )
    return items[:limit]
