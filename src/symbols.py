"""
Indian market symbol handling.

Accepts the formats retail investors actually type and normalises them into a
single canonical form used across the pipeline:

    RELIANCE          -> NSE equity  (Yahoo: RELIANCE.NS)
    RELIANCE.NS       -> NSE equity
    TCS.BO / 532540   -> BSE equity  (Yahoo: 532540.BO; numeric codes are BSE scrip codes)
    NIFTY / NIFTY50   -> NIFTY 50 index (^NSEI)
    BANKNIFTY         -> NIFTY Bank index (^NSEBANK)
    SENSEX            -> BSE SENSEX (^BSESN)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Yahoo Finance tickers for the Indian indices used in market context.
INDEX_SYMBOLS = {
    "NIFTY 50": "^NSEI",
    "SENSEX": "^BSESN",
    "NIFTY BANK": "^NSEBANK",
    "NIFTY IT": "^CNXIT",
    "NIFTY MIDCAP 50": "^NSEMDCP50",
    "INDIA VIX": "^INDIAVIX",
    "USD/INR": "INR=X",
    "BRENT CRUDE": "BZ=F",
}

# Aliases users may pass in STOCK_LIST that mean an index, not an equity.
_INDEX_ALIASES = {
    "NIFTY": "^NSEI",
    "NIFTY50": "^NSEI",
    "NIFTY 50": "^NSEI",
    "^NSEI": "^NSEI",
    "SENSEX": "^BSESN",
    "^BSESN": "^BSESN",
    "BANKNIFTY": "^NSEBANK",
    "NIFTYBANK": "^NSEBANK",
    "^NSEBANK": "^NSEBANK",
    "INDIAVIX": "^INDIAVIX",
    "INDIA VIX": "^INDIAVIX",
    "^INDIAVIX": "^INDIAVIX",
}

_BSE_SCRIP_RE = re.compile(r"^\d{6}$")
_VALID_NSE_RE = re.compile(r"^[A-Z0-9&\-]{1,20}$")


@dataclass(frozen=True)
class StockSymbol:
    """Canonical representation of one instrument."""

    raw: str          # what the user typed
    symbol: str       # exchange symbol without suffix (RELIANCE, 532540, ^NSEI)
    exchange: str     # "NSE" | "BSE" | "INDEX"
    yahoo: str        # ticker used against Yahoo Finance (RELIANCE.NS, 532540.BO, ^NSEI)

    @property
    def is_index(self) -> bool:
        return self.exchange == "INDEX"

    @property
    def display(self) -> str:
        if self.is_index:
            for name, ticker in INDEX_SYMBOLS.items():
                if ticker == self.yahoo:
                    return name
            return self.symbol
        return f"{self.symbol} ({self.exchange})"


class SymbolError(ValueError):
    """Raised when an input cannot be interpreted as an Indian instrument."""


def parse_symbol(raw: str) -> StockSymbol:
    """Normalise one user-supplied token into a StockSymbol."""
    if raw is None:
        raise SymbolError("empty symbol")
    token = raw.strip().upper()
    if not token:
        raise SymbolError("empty symbol")

    # Index aliases first (before suffix logic).
    if token in _INDEX_ALIASES:
        ticker = _INDEX_ALIASES[token]
        return StockSymbol(raw=raw, symbol=ticker, exchange="INDEX", yahoo=ticker)
    if token.startswith("^"):
        return StockSymbol(raw=raw, symbol=token, exchange="INDEX", yahoo=token)

    # Explicit exchange suffixes: RELIANCE.NS / 532540.BO / RELIANCE.NSE / TCS.BSE
    m = re.match(r"^(.+)\.(NS|NSE)$", token)
    if m:
        base = m.group(1)
        _validate_equity(base)
        return StockSymbol(raw=raw, symbol=base, exchange="NSE", yahoo=f"{base}.NS")
    m = re.match(r"^(.+)\.(BO|BSE)$", token)
    if m:
        base = m.group(1)
        _validate_equity(base)
        return StockSymbol(raw=raw, symbol=base, exchange="BSE", yahoo=f"{base}.BO")

    # Six-digit numeric codes are BSE scrip codes (e.g. 500325 = Reliance).
    if _BSE_SCRIP_RE.match(token):
        return StockSymbol(raw=raw, symbol=token, exchange="BSE", yahoo=f"{token}.BO")

    # Bare symbol defaults to NSE — where >90% of Indian liquidity is.
    _validate_equity(token)
    return StockSymbol(raw=raw, symbol=token, exchange="NSE", yahoo=f"{token}.NS")


def _validate_equity(symbol: str) -> None:
    if not _VALID_NSE_RE.match(symbol):
        raise SymbolError(f"'{symbol}' does not look like a valid NSE/BSE symbol")


def parse_watchlist(tokens: list[str]) -> tuple[list[StockSymbol], list[str]]:
    """Parse a list of tokens; returns (parsed, rejected_raw_tokens)."""
    parsed: list[StockSymbol] = []
    rejected: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        try:
            sym = parse_symbol(token)
        except SymbolError:
            rejected.append(token)
            continue
        if sym.yahoo in seen:
            continue
        seen.add(sym.yahoo)
        parsed.append(sym)
    return parsed, rejected
