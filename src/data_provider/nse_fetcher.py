"""
Direct NSE India fetcher for signals Yahoo cannot provide:

* delivery percentage (what fraction of traded quantity was actually taken
  as delivery — a classic quality-of-move signal in Indian markets)
* price band / circuit limits
* corporate announcements
* market-wide FII / DII provisional cash flows

nseindia.com requires a browser-like session (cookies set on the homepage)
and throttles aggressively, so every call here is best-effort: any failure
degrades to None/empty and the pipeline continues on Yahoo data alone.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

from src.data_provider.base import NseExtras
from src.symbols import StockSymbol

logger = logging.getLogger(__name__)

_BASE = "https://www.nseindia.com"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}


class NseClient:
    """Thin session-cookie-aware client for nseindia.com JSON endpoints."""

    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self._session: Optional[requests.Session] = None

    def _get_session(self) -> Optional[requests.Session]:
        if self._session is not None:
            return self._session
        session = requests.Session()
        session.headers.update(_HEADERS)
        try:
            # Homepage visit sets the cookies the API endpoints require.
            session.get(_BASE, timeout=self.timeout)
        except Exception as exc:
            logger.warning("NSE session warmup failed: %s", exc)
            return None
        self._session = session
        return session

    def _get_json(self, path: str, params: Optional[Dict[str, str]] = None) -> Optional[Any]:
        session = self._get_session()
        if session is None:
            return None
        try:
            resp = session.get(f"{_BASE}{path}", params=params, timeout=self.timeout)
            if resp.status_code != 200:
                logger.warning("NSE %s returned HTTP %s", path, resp.status_code)
                return None
            return resp.json()
        except Exception as exc:
            logger.warning("NSE %s failed: %s", path, exc)
            return None

    # ------------------------------------------------------------------ equity
    def fetch_extras(self, symbol: StockSymbol) -> NseExtras:
        """Delivery %, circuit band, F&O membership and announcements for one NSE stock."""
        extras = NseExtras()
        if symbol.exchange != "NSE" or symbol.is_index:
            return extras

        data = self._get_json(
            "/api/quote-equity", params={"symbol": symbol.symbol, "section": "trade_info"}
        )
        if isinstance(data, dict):
            sec = data.get("securityWiseDP") or {}
            try:
                pct = sec.get("deliveryToTradedQuantity")
                if pct is not None:
                    extras.delivery_pct = float(pct)
            except (TypeError, ValueError):
                pass

        info = self._get_json("/api/quote-equity", params={"symbol": symbol.symbol})
        if isinstance(info, dict):
            price_info = info.get("priceInfo") or {}
            try:
                extras.upper_circuit = float(price_info.get("upperCP"))
            except (TypeError, ValueError):
                pass
            try:
                extras.lower_circuit = float(price_info.get("lowerCP"))
            except (TypeError, ValueError):
                pass
            meta = info.get("info") or {}
            if isinstance(meta.get("isFNOSec"), bool):
                extras.is_fno = meta["isFNOSec"]
            industry_info = info.get("industryInfo") or {}
            extras.industry = str(industry_info.get("industry") or "")

        ann = self._get_json(
            "/api/corporate-announcements", params={"index": "equities", "symbol": symbol.symbol}
        )
        if isinstance(ann, list):
            for item in ann[:5]:
                if not isinstance(item, dict):
                    continue
                extras.announcements.append(
                    {
                        "date": str(item.get("an_dt") or item.get("sort_date") or ""),
                        "subject": str(item.get("desc") or item.get("subject") or ""),
                        "detail": str(item.get("attchmntText") or "")[:300],
                    }
                )
        return extras

    # ------------------------------------------------------------- market wide
    def fetch_fii_dii(self) -> List[Dict[str, Any]]:
        """Provisional FII/DII cash market flows (₹ crore) for the latest session."""
        data = self._get_json("/api/fiidiiTradeReact")
        rows: List[Dict[str, Any]] = []
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                rows.append(
                    {
                        "category": str(item.get("category") or ""),
                        "date": str(item.get("date") or ""),
                        "buy_value": _to_float(item.get("buyValue")),
                        "sell_value": _to_float(item.get("sellValue")),
                        "net_value": _to_float(item.get("netValue")),
                    }
                )
        return rows


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
