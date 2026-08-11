"""
Market-wide context for the day: benchmark indices, India VIX, currency,
crude oil (a key India macro input) and FII/DII provisional flows.

The LLM receives this so single-stock advice is framed by overall regime
(e.g. don't recommend aggressive longs into a spiking VIX + heavy FII selling).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.config import Config
from src.data_provider.manager import DataManager
from src.symbols import INDEX_SYMBOLS, StockSymbol

logger = logging.getLogger(__name__)


@dataclass
class IndexSnapshot:
    name: str
    level: Optional[float] = None
    change_pct: Optional[float] = None
    return_5d_pct: Optional[float] = None
    return_20d_pct: Optional[float] = None


@dataclass
class MarketContext:
    indices: List[IndexSnapshot] = field(default_factory=list)
    fii_dii: List[Dict] = field(default_factory=list)
    as_of: str = ""

    def get(self, name: str) -> Optional[IndexSnapshot]:
        for idx in self.indices:
            if idx.name == name:
                return idx
        return None

    @property
    def regime_hint(self) -> str:
        """A one-line regime read derived from NIFTY trend + VIX + flows."""
        parts: List[str] = []
        nifty = self.get("NIFTY 50")
        if nifty and nifty.change_pct is not None:
            direction = "up" if nifty.change_pct >= 0 else "down"
            parts.append(f"NIFTY {direction} {abs(nifty.change_pct):.2f}% today")
        vix = self.get("INDIA VIX")
        if vix and vix.level is not None:
            if vix.level >= 20:
                parts.append(f"India VIX elevated at {vix.level:.1f} (risk-off)")
            elif vix.level <= 12:
                parts.append(f"India VIX low at {vix.level:.1f} (complacent/calm)")
            else:
                parts.append(f"India VIX moderate at {vix.level:.1f}")
        fii_net = self.fii_net()
        if fii_net is not None:
            side = "buying" if fii_net >= 0 else "selling"
            parts.append(f"FII net {side} ₹{abs(fii_net):,.0f} cr (provisional)")
        return "; ".join(parts) if parts else "market context unavailable"

    def fii_net(self) -> Optional[float]:
        for row in self.fii_dii:
            if "FII" in row.get("category", "").upper():
                return row.get("net_value")
        return None

    def dii_net(self) -> Optional[float]:
        for row in self.fii_dii:
            if "DII" in row.get("category", "").upper():
                return row.get("net_value")
        return None

    def to_prompt_text(self) -> str:
        lines = ["## Indian Market Context"]
        for idx in self.indices:
            if idx.level is None:
                continue
            chg = f"{idx.change_pct:+.2f}%" if idx.change_pct is not None else "n/a"
            r5 = f"{idx.return_5d_pct:+.1f}%" if idx.return_5d_pct is not None else "n/a"
            r20 = f"{idx.return_20d_pct:+.1f}%" if idx.return_20d_pct is not None else "n/a"
            lines.append(f"- {idx.name}: {idx.level:,.2f} ({chg} today, {r5} 5d, {r20} 20d)")
        fii, dii = self.fii_net(), self.dii_net()
        if fii is not None or dii is not None:
            fii_txt = f"₹{fii:,.0f} cr" if fii is not None else "n/a"
            dii_txt = f"₹{dii:,.0f} cr" if dii is not None else "n/a"
            lines.append(f"- Provisional cash flows — FII net: {fii_txt}, DII net: {dii_txt}")
        lines.append(f"- Regime read: {self.regime_hint}")
        return "\n".join(lines)


def build_market_context(config: Config, manager: DataManager) -> MarketContext:
    """Fetch all index snapshots + FII/DII flows. Failures degrade gracefully."""
    from src.data_provider import yahoo_fetcher

    ctx = MarketContext()
    for name, ticker in INDEX_SYMBOLS.items():
        sym = StockSymbol(raw=name, symbol=ticker, exchange="INDEX", yahoo=ticker)
        try:
            bars = yahoo_fetcher.fetch_daily_bars(sym, days=120)
        except Exception as exc:
            logger.warning("index fetch failed for %s: %s", name, exc)
            bars = None
        snap = IndexSnapshot(name=name)
        if bars is not None and len(bars) >= 2:
            close = bars["close"]
            snap.level = float(close.iloc[-1])
            prev = float(close.iloc[-2])
            if prev:
                snap.change_pct = (snap.level / prev - 1) * 100
            if len(close) > 5 and close.iloc[-6]:
                snap.return_5d_pct = float((close.iloc[-1] / close.iloc[-6] - 1) * 100)
            if len(close) > 20 and close.iloc[-21]:
                snap.return_20d_pct = float((close.iloc[-1] / close.iloc[-21] - 1) * 100)
            ctx.as_of = bars.index[-1].strftime("%Y-%m-%d")
        ctx.indices.append(snap)

    ctx.fii_dii = manager.fetch_fii_dii()
    return ctx
