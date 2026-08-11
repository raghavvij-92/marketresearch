import numpy as np
import pandas as pd

from src.indicators import (
    MIN_BARS,
    compute_atr,
    compute_macd,
    compute_rsi,
    compute_snapshot,
)


def test_snapshot_uptrend(uptrend_bars):
    snap = compute_snapshot(uptrend_bars)
    assert snap.close > 0
    assert snap.sma[5] is not None and snap.sma[200] is not None
    assert snap.trend_score > 55, "steady uptrend should score bullish"
    assert snap.close > snap.sma[200]
    assert snap.week52_high >= snap.close >= snap.week52_low
    assert snap.atr14 is not None and snap.atr14 > 0
    assert snap.rsi14 is not None and 0 <= snap.rsi14 <= 100


def test_snapshot_downtrend(downtrend_bars):
    snap = compute_snapshot(downtrend_bars)
    assert snap.trend_score < 45, "steady downtrend should score bearish"
    assert snap.close < snap.sma[200]


def test_snapshot_insufficient_data(uptrend_bars):
    snap = compute_snapshot(uptrend_bars.head(MIN_BARS - 1))
    assert snap.close == 0.0
    assert snap.trend_score == 50


def test_rsi_bounds_and_extremes():
    always_up = pd.Series(np.linspace(100, 200, 60))
    rsi = compute_rsi(always_up)
    assert rsi.iloc[-1] > 90
    always_down = pd.Series(np.linspace(200, 100, 60))
    rsi = compute_rsi(always_down)
    assert rsi.iloc[-1] < 10


def test_macd_shapes(uptrend_bars):
    macd, sig, hist = compute_macd(uptrend_bars["close"])
    assert len(macd) == len(uptrend_bars)
    pd.testing.assert_series_equal(hist, macd - sig)


def test_atr_positive(uptrend_bars):
    atr = compute_atr(uptrend_bars)
    assert (atr.dropna() > 0).all()


def test_support_resistance_bracket_price(uptrend_bars):
    snap = compute_snapshot(uptrend_bars)
    if snap.support is not None:
        assert snap.support < snap.close
    if snap.resistance is not None:
        assert snap.resistance > snap.close


def test_pivot_ordering(uptrend_bars):
    snap = compute_snapshot(uptrend_bars)
    assert snap.pivot_s1 <= snap.pivot <= snap.pivot_r1


def test_to_dict_rounds(uptrend_bars):
    d = compute_snapshot(uptrend_bars).to_dict()
    assert isinstance(d["close"], float)
    assert d["trend_score"] == int(d["trend_score"])
