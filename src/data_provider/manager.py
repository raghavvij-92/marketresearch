"""Orchestrates the provider layer: Yahoo backbone + optional NSE enrichment."""

from __future__ import annotations

import logging
from typing import List, Optional

from src.config import Config
from src.data_provider import nse_fetcher, yahoo_fetcher
from src.data_provider.base import StockData
from src.symbols import StockSymbol

logger = logging.getLogger(__name__)


class DataManager:
    def __init__(self, config: Config):
        self.config = config
        self.nse_client: Optional[nse_fetcher.NseClient] = (
            nse_fetcher.NseClient(timeout=config.request_timeout)
            if config.enable_nse_direct
            else None
        )

    def fetch_stock(self, symbol: StockSymbol) -> StockData:
        """Pull everything for one stock; partial failures are recorded, not fatal."""
        errors: List[str] = []

        bars = yahoo_fetcher.fetch_daily_bars(symbol, days=self.config.history_days)
        if bars is None or bars.empty:
            errors.append("no daily price history available")
            import pandas as pd

            bars = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        quote = yahoo_fetcher.quote_from_bars(bars)
        fundamentals = yahoo_fetcher.fetch_fundamentals(symbol)

        data = StockData(
            symbol=symbol, bars=bars, quote=quote, fundamentals=fundamentals, errors=errors
        )

        if self.nse_client is not None and symbol.exchange == "NSE":
            try:
                data.nse = self.nse_client.fetch_extras(symbol)
            except Exception as exc:  # never let NSE enrichment break the run
                logger.warning("NSE enrichment failed for %s: %s", symbol.symbol, exc)
                errors.append(f"NSE enrichment failed: {exc}")
        return data

    def fetch_fii_dii(self):
        if self.nse_client is None:
            return []
        try:
            return self.nse_client.fetch_fii_dii()
        except Exception as exc:
            logger.warning("FII/DII fetch failed: %s", exc)
            return []
