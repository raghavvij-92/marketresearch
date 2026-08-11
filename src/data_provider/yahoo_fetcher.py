"""
Yahoo Finance fetcher — the primary, keyless data source.

NSE equities resolve as SYMBOL.NS, BSE as CODE.BO, indices as ^NSEI etc.

Implementation notes: the public chart API (v8) serves daily OHLCV without
authentication, and quoteSummary (v10) serves fundamentals once a session
cookie + crumb are obtained. Both are called directly through `requests`
(which honours standard proxy/CA configuration), with the `yfinance` library
kept as a fallback path for environments where the direct calls fail.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

import pandas as pd
import requests

from src.data_provider.base import Fundamentals, Quote
from src.symbols import StockSymbol

logger = logging.getLogger(__name__)

_BAR_COLUMNS = ["open", "high", "low", "close", "volume"]
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_TIMEOUT = 25


class _YahooSession:
    """Shared requests session that lazily acquires the Yahoo cookie + crumb."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._session: Optional[requests.Session] = None
        self._crumb: Optional[str] = None

    def session(self) -> requests.Session:
        with self._lock:
            if self._session is None:
                s = requests.Session()
                # NB: Yahoo's crumb endpoint rejects "Accept: application/json"
                # with HTTP 406, so keep a permissive Accept header.
                s.headers.update({"User-Agent": _UA, "Accept": "*/*"})
                self._session = s
            return self._session

    def crumb(self) -> Optional[str]:
        with self._lock:
            if self._crumb is not None:
                return self._crumb
        s = self.session()
        try:
            # fc.yahoo.com 404s but sets the auth cookie needed for the crumb.
            try:
                s.get("https://fc.yahoo.com", timeout=_TIMEOUT)
            except requests.RequestException:
                pass
            resp = s.get("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=_TIMEOUT)
            if resp.status_code == 200 and resp.text and "<" not in resp.text:
                with self._lock:
                    self._crumb = resp.text.strip()
                return self._crumb
        except requests.RequestException as exc:
            logger.warning("Yahoo crumb acquisition failed: %s", exc)
        return None


_yahoo = _YahooSession()


# ------------------------------------------------------------------------- bars


def fetch_daily_bars(symbol: StockSymbol, days: int = 400) -> Optional[pd.DataFrame]:
    """Daily OHLCV as an ascending DatetimeIndex DataFrame, or None on failure."""
    df = _fetch_bars_direct(symbol, days)
    if df is None:
        df = _fetch_bars_yfinance(symbol, days)
    return df


def _range_param(days: int) -> str:
    for cap, label in ((7, "5d"), (32, "1mo"), (95, "3mo"), (185, "6mo"), (366, "1y"), (735, "2y")):
        if days <= cap:
            return label
    return "5y"


def _fetch_bars_direct(symbol: StockSymbol, days: int) -> Optional[pd.DataFrame]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol.yahoo}"
    try:
        resp = _yahoo.session().get(
            url,
            params={"range": _range_param(days), "interval": "1d", "events": "div,splits"},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.warning("Yahoo chart HTTP %s for %s", resp.status_code, symbol.yahoo)
            return None
        result = (resp.json().get("chart") or {}).get("result") or []
        if not result:
            return None
        payload = result[0]
        timestamps = payload.get("timestamp") or []
        quote = ((payload.get("indicators") or {}).get("quote") or [{}])[0]
        if not timestamps or not quote:
            return None
        df = pd.DataFrame(
            {
                "open": quote.get("open"),
                "high": quote.get("high"),
                "low": quote.get("low"),
                "close": quote.get("close"),
                "volume": quote.get("volume"),
            },
            index=pd.to_datetime(timestamps, unit="s"),
        )
        # Timestamps are exchange-local session opens in UTC; normalise to dates.
        df.index = df.index.tz_localize("UTC").tz_convert("Asia/Kolkata").tz_localize(None).normalize()
        df = df[df["close"].notna() & (df["close"] > 0)]
        df = df[~df.index.duplicated(keep="last")]
        df.sort_index(inplace=True)
        return df if not df.empty else None
    except Exception as exc:
        logger.warning("Yahoo direct chart fetch failed for %s: %s", symbol.yahoo, exc)
        return None


def _fetch_bars_yfinance(symbol: StockSymbol, days: int) -> Optional[pd.DataFrame]:
    try:
        import yfinance as yf
        from datetime import datetime, timedelta

        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        df = yf.Ticker(symbol.yahoo).history(start=start, interval="1d", auto_adjust=False)
    except Exception as exc:
        logger.warning("yfinance fallback failed for %s: %s", symbol.yahoo, exc)
        return None
    if df is None or df.empty:
        return None
    df = df.rename(columns={c: c.lower() for c in df.columns})
    if any(c not in df.columns for c in _BAR_COLUMNS):
        return None
    df = df[_BAR_COLUMNS].copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df = df[df["close"].notna() & (df["close"] > 0)]
    df.sort_index(inplace=True)
    return df


# ------------------------------------------------------------------------ quote


def quote_from_bars(bars: pd.DataFrame) -> Quote:
    """Derive a quote from the last two daily bars (robust when live quote APIs fail)."""
    quote = Quote()
    if bars is None or bars.empty:
        return quote
    last = bars.iloc[-1]
    quote.price = float(last["close"])
    quote.open = _safe_float(last["open"])
    quote.high = _safe_float(last["high"])
    quote.low = _safe_float(last["low"])
    quote.volume = _safe_float(last["volume"])
    quote.as_of = bars.index[-1].strftime("%Y-%m-%d")
    if len(bars) >= 2:
        prev = float(bars.iloc[-2]["close"])
        quote.prev_close = prev
        if prev:
            quote.change = quote.price - prev
            quote.change_pct = (quote.price - prev) / prev * 100.0
    window = bars.tail(252)
    quote.week52_high = float(window["high"].max())
    quote.week52_low = float(window["low"].min())
    return quote


def _safe_float(value: Any) -> Optional[float]:
    try:
        result = float(value)
        return None if pd.isna(result) else result
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------- fundamentals

_MODULES = "summaryDetail,defaultKeyStatistics,financialData,assetProfile,price,quoteType"


def fetch_fundamentals(symbol: StockSymbol) -> Fundamentals:
    """Best-effort fundamentals; direct quoteSummary first, yfinance fallback."""
    if symbol.is_index:
        return Fundamentals()
    fund = _fetch_fundamentals_direct(symbol)
    if fund is None:
        fund = _fetch_fundamentals_yfinance(symbol)
    return fund or Fundamentals()


def _raw(module: Dict[str, Any], key: str, scale: float = 1.0) -> Optional[float]:
    node = module.get(key)
    if isinstance(node, dict):
        node = node.get("raw")
    if isinstance(node, (int, float)) and not isinstance(node, bool):
        return float(node) * scale
    return None


def _fetch_fundamentals_direct(symbol: StockSymbol) -> Optional[Fundamentals]:
    crumb = _yahoo.crumb()
    if not crumb:
        return None
    try:
        resp = _yahoo.session().get(
            f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol.yahoo}",
            params={"modules": _MODULES, "crumb": crumb},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.warning("Yahoo quoteSummary HTTP %s for %s", resp.status_code, symbol.yahoo)
            return None
        result = (resp.json().get("quoteSummary") or {}).get("result") or []
        if not result:
            return None
        data = result[0]
    except Exception as exc:
        logger.warning("Yahoo quoteSummary failed for %s: %s", symbol.yahoo, exc)
        return None

    summary = data.get("summaryDetail") or {}
    stats = data.get("defaultKeyStatistics") or {}
    fin = data.get("financialData") or {}
    profile = data.get("assetProfile") or {}
    price = data.get("price") or {}
    quote_type = data.get("quoteType") or {}

    fund = Fundamentals()
    fund.market_cap = _raw(summary, "marketCap") or _raw(price, "marketCap")
    fund.trailing_pe = _raw(summary, "trailingPE")
    fund.forward_pe = _raw(summary, "forwardPE") or _raw(stats, "forwardPE")
    fund.price_to_book = _raw(stats, "priceToBook")
    fund.trailing_eps = _raw(stats, "trailingEps")
    dividend_yield = _raw(summary, "dividendYield")
    if dividend_yield is not None:
        fund.dividend_yield = dividend_yield * 100 if dividend_yield < 0.5 else dividend_yield
    fund.return_on_equity = _raw(fin, "returnOnEquity", 100.0)
    fund.debt_to_equity = _raw(fin, "debtToEquity")
    fund.revenue_growth = _raw(fin, "revenueGrowth", 100.0)
    fund.earnings_growth = _raw(fin, "earningsGrowth", 100.0)
    fund.profit_margin = _raw(fin, "profitMargins", 100.0)
    fund.beta = _raw(summary, "beta") or _raw(stats, "beta")
    fund.sector = str(profile.get("sector") or "")
    fund.industry = str(profile.get("industry") or "")
    fund.long_name = str(
        price.get("longName") or quote_type.get("longName") or quote_type.get("shortName") or ""
    )
    return fund


def _fetch_fundamentals_yfinance(symbol: StockSymbol) -> Optional[Fundamentals]:
    try:
        import yfinance as yf

        info = yf.Ticker(symbol.yahoo).info or {}
    except Exception as exc:
        logger.warning("yfinance info fallback failed for %s: %s", symbol.yahoo, exc)
        return None

    def _num(key: str, scale: float = 1.0) -> Optional[float]:
        val = info.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return float(val) * scale
        return None

    fund = Fundamentals()
    fund.market_cap = _num("marketCap")
    fund.trailing_pe = _num("trailingPE")
    fund.forward_pe = _num("forwardPE")
    fund.price_to_book = _num("priceToBook")
    fund.trailing_eps = _num("trailingEps")
    fund.dividend_yield = _num("dividendYield")
    if fund.dividend_yield is not None and fund.dividend_yield < 0.5:
        fund.dividend_yield *= 100.0
    fund.return_on_equity = _num("returnOnEquity", 100.0)
    fund.debt_to_equity = _num("debtToEquity")
    fund.revenue_growth = _num("revenueGrowth", 100.0)
    fund.earnings_growth = _num("earningsGrowth", 100.0)
    fund.profit_margin = _num("profitMargins", 100.0)
    fund.beta = _num("beta")
    fund.sector = str(info.get("sector") or "")
    fund.industry = str(info.get("industry") or "")
    fund.long_name = str(info.get("longName") or info.get("shortName") or "")
    return fund
