import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_provider.base import StockData  # noqa: E402
from src.data_provider.yahoo_fetcher import quote_from_bars  # noqa: E402
from src.symbols import parse_symbol  # noqa: E402


def make_bars(days: int = 300, trend: float = 0.001, seed: int = 42) -> pd.DataFrame:
    """Synthetic but realistic daily OHLCV with a mild drift."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end="2026-08-10", periods=days)
    returns = rng.normal(trend, 0.015, days)
    close = 1000.0 * np.exp(np.cumsum(returns))
    open_ = close * (1 + rng.normal(0, 0.004, days))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, days)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, days)))
    volume = rng.integers(1_000_000, 5_000_000, days).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


@pytest.fixture
def uptrend_bars() -> pd.DataFrame:
    return make_bars(trend=0.003, seed=7)


@pytest.fixture
def downtrend_bars() -> pd.DataFrame:
    return make_bars(trend=-0.003, seed=7)


@pytest.fixture
def stock_data(uptrend_bars) -> StockData:
    sym = parse_symbol("RELIANCE")
    return StockData(symbol=sym, bars=uptrend_bars, quote=quote_from_bars(uptrend_bars))
