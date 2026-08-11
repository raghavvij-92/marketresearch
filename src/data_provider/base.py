"""Shared data contracts for the provider layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from src.symbols import StockSymbol


@dataclass
class Quote:
    """Latest traded snapshot for one instrument."""

    price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    prev_close: Optional[float] = None
    volume: Optional[float] = None
    week52_high: Optional[float] = None
    week52_low: Optional[float] = None
    currency: str = "INR"
    as_of: str = ""


@dataclass
class Fundamentals:
    """Valuation / quality snapshot (best effort — fields may be None)."""

    market_cap: Optional[float] = None          # in INR
    trailing_pe: Optional[float] = None
    forward_pe: Optional[float] = None
    price_to_book: Optional[float] = None
    trailing_eps: Optional[float] = None
    dividend_yield: Optional[float] = None      # percent
    return_on_equity: Optional[float] = None    # percent
    debt_to_equity: Optional[float] = None
    revenue_growth: Optional[float] = None      # percent, yoy
    earnings_growth: Optional[float] = None     # percent, yoy
    profit_margin: Optional[float] = None       # percent
    beta: Optional[float] = None
    sector: str = ""
    industry: str = ""
    long_name: str = ""

    @property
    def market_cap_category(self) -> str:
        """SEBI-style buckets (approximate, by full market cap in ₹ crore)."""
        if self.market_cap is None:
            return "Unknown"
        crore = self.market_cap / 1e7
        if crore >= 50_000:
            return "Large Cap"
        if crore >= 17_000:
            return "Mid Cap"
        return "Small Cap"


@dataclass
class NseExtras:
    """India-specific enrichment available only from NSE's own endpoints."""

    delivery_pct: Optional[float] = None        # % of traded qty actually delivered
    announcements: List[Dict[str, str]] = field(default_factory=list)
    upper_circuit: Optional[float] = None
    lower_circuit: Optional[float] = None
    is_fno: Optional[bool] = None               # in the derivatives (F&O) segment?
    industry: str = ""


@dataclass
class StockData:
    """Everything the analyzer needs for one stock."""

    symbol: StockSymbol
    bars: pd.DataFrame                          # daily OHLCV, DatetimeIndex ascending
    quote: Quote
    fundamentals: Fundamentals = field(default_factory=Fundamentals)
    nse: NseExtras = field(default_factory=NseExtras)
    errors: List[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.fundamentals.long_name or self.symbol.symbol

    @property
    def ok(self) -> bool:
        return self.bars is not None and len(self.bars) >= 30

    def summary_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol.symbol,
            "exchange": self.symbol.exchange,
            "name": self.name,
            "price": self.quote.price,
            "change_pct": self.quote.change_pct,
            "bars": 0 if self.bars is None else len(self.bars),
            "errors": self.errors,
        }
