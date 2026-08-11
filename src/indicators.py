"""
Technical indicator engine.

Pure pandas/numpy — no TA-lib dependency — computing everything the analyzer
and the LLM prompt need from a daily OHLCV frame:

* trend:    SMA 5/10/20/50/200, EMA 12/26, MA alignment + trend score
* momentum: RSI(14), MACD(12,26,9), Stochastic(14,3)
* volatility: Bollinger(20,2), ATR(14)
* volume:   volume ratio vs 20d average, OBV slope
* structure: 52-week position, swing support/resistance, classic pivot points
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

MIN_BARS = 30


@dataclass
class TechnicalSnapshot:
    """All computed indicator values for the latest bar."""

    close: float = 0.0
    change_pct: Optional[float] = None

    sma: Dict[int, Optional[float]] = field(default_factory=dict)   # 5/10/20/50/200
    ma_alignment: str = ""            # e.g. "P > MA5 > MA10 > MA20 (bullish stack)"
    is_bullish_stack: bool = False
    is_bearish_stack: bool = False
    bias_ma5_pct: Optional[float] = None     # (close - MA5)/MA5 * 100
    bias_ma20_pct: Optional[float] = None

    rsi14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    macd_cross: str = ""              # "bullish crossover" / "bearish crossover" / ""
    stoch_k: Optional[float] = None
    stoch_d: Optional[float] = None

    bb_upper: Optional[float] = None
    bb_mid: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_pct_b: Optional[float] = None  # 0 at lower band, 1 at upper band
    atr14: Optional[float] = None
    atr_pct: Optional[float] = None   # ATR as % of close

    volume: Optional[float] = None
    volume_ratio: Optional[float] = None   # today vs 20d average
    volume_status: str = ""                # "surge" / "elevated" / "normal" / "dry-up"
    obv_slope_20d: Optional[float] = None  # normalised OBV slope, +ve = accumulation

    week52_high: Optional[float] = None
    week52_low: Optional[float] = None
    pct_from_52w_high: Optional[float] = None
    pct_from_52w_low: Optional[float] = None

    support: Optional[float] = None
    resistance: Optional[float] = None
    pivot: Optional[float] = None
    pivot_r1: Optional[float] = None
    pivot_s1: Optional[float] = None

    return_5d_pct: Optional[float] = None
    return_20d_pct: Optional[float] = None
    return_60d_pct: Optional[float] = None

    trend_score: int = 50             # 0-100 composite

    def to_dict(self) -> Dict:
        out = {}
        for key, value in self.__dict__.items():
            if isinstance(value, dict):
                out[key] = {k: _round(v) for k, v in value.items()}
            elif isinstance(value, float):
                out[key] = _round(value)
            else:
                out[key] = value
        return out


def _round(value, digits: int = 2):
    if isinstance(value, float):
        return round(value, digits)
    return value


def _last(series: pd.Series) -> Optional[float]:
    if series is None or len(series) == 0:
        return None
    val = series.iloc[-1]
    if pd.isna(val):
        return None
    return float(val)


# --------------------------------------------------------------------------- core


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    return rsi.fillna(100.0).where(avg_loss.notna(), np.nan)


def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    sig = macd.ewm(span=signal, adjust=False).mean()
    return macd, sig, macd - sig


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def compute_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3):
    low_min = df["low"].rolling(k_period).min()
    high_max = df["high"].rolling(k_period).max()
    rng = (high_max - low_min).replace(0.0, np.nan)
    k = (df["close"] - low_min) / rng * 100
    d = k.rolling(d_period).mean()
    return k, d


def compute_obv(df: pd.DataFrame) -> pd.Series:
    direction = np.sign(df["close"].diff()).fillna(0.0)
    return (direction * df["volume"]).cumsum()


def swing_levels(df: pd.DataFrame, lookback: int = 60, window: int = 5):
    """Nearest swing support below and resistance above the last close."""
    recent = df.tail(lookback)
    close = float(recent["close"].iloc[-1])
    highs: List[float] = []
    lows: List[float] = []
    h, l = recent["high"].values, recent["low"].values
    for i in range(window, len(recent) - window):
        if h[i] == max(h[i - window : i + window + 1]):
            highs.append(float(h[i]))
        if l[i] == min(l[i - window : i + window + 1]):
            lows.append(float(l[i]))
    support = max([x for x in lows if x < close], default=None)
    resistance = min([x for x in highs if x > close], default=None)
    return support, resistance


# ---------------------------------------------------------------------- snapshot


def compute_snapshot(df: pd.DataFrame) -> TechnicalSnapshot:
    """Compute the full technical snapshot for the most recent bar."""
    snap = TechnicalSnapshot()
    if df is None or len(df) < MIN_BARS:
        return snap

    close = df["close"]
    snap.close = float(close.iloc[-1])
    if len(close) >= 2 and close.iloc[-2]:
        snap.change_pct = float((close.iloc[-1] / close.iloc[-2] - 1) * 100)

    # Moving averages -----------------------------------------------------------
    for period in (5, 10, 20, 50, 200):
        snap.sma[period] = _last(close.rolling(period).mean()) if len(close) >= period else None

    ma5, ma10, ma20 = snap.sma.get(5), snap.sma.get(10), snap.sma.get(20)
    if all(v is not None for v in (ma5, ma10, ma20)):
        if snap.close > ma5 > ma10 > ma20:
            snap.ma_alignment = "Price > MA5 > MA10 > MA20 (bullish stack)"
            snap.is_bullish_stack = True
        elif snap.close < ma5 < ma10 < ma20:
            snap.ma_alignment = "Price < MA5 < MA10 < MA20 (bearish stack)"
            snap.is_bearish_stack = True
        else:
            snap.ma_alignment = "Mixed / transitioning moving averages"
        snap.bias_ma5_pct = (snap.close - ma5) / ma5 * 100
        snap.bias_ma20_pct = (snap.close - ma20) / ma20 * 100

    # Momentum ------------------------------------------------------------------
    rsi = compute_rsi(close)
    snap.rsi14 = _last(rsi)
    macd, sig, hist = compute_macd(close)
    snap.macd, snap.macd_signal, snap.macd_hist = _last(macd), _last(sig), _last(hist)
    if len(hist) >= 2 and not pd.isna(hist.iloc[-2]) and not pd.isna(hist.iloc[-1]):
        if hist.iloc[-2] <= 0 < hist.iloc[-1]:
            snap.macd_cross = "bullish crossover (MACD crossed above signal)"
        elif hist.iloc[-2] >= 0 > hist.iloc[-1]:
            snap.macd_cross = "bearish crossover (MACD crossed below signal)"
    k, d = compute_stochastic(df)
    snap.stoch_k, snap.stoch_d = _last(k), _last(d)

    # Volatility ----------------------------------------------------------------
    if len(close) >= 20:
        mid = close.rolling(20).mean()
        std = close.rolling(20).std()
        snap.bb_mid = _last(mid)
        upper, lower = mid + 2 * std, mid - 2 * std
        snap.bb_upper, snap.bb_lower = _last(upper), _last(lower)
        if (
            snap.bb_upper is not None
            and snap.bb_lower is not None
            and snap.bb_upper != snap.bb_lower
        ):
            snap.bb_pct_b = (snap.close - snap.bb_lower) / (snap.bb_upper - snap.bb_lower)
    atr = compute_atr(df)
    snap.atr14 = _last(atr)
    if snap.atr14 is not None and snap.close:
        snap.atr_pct = snap.atr14 / snap.close * 100

    # Volume --------------------------------------------------------------------
    vol = df["volume"]
    snap.volume = _last(vol)
    if len(vol) >= 21:
        avg20 = float(vol.iloc[-21:-1].mean())
        if avg20 > 0 and snap.volume is not None:
            snap.volume_ratio = snap.volume / avg20
            if snap.volume_ratio >= 2.0:
                snap.volume_status = "surge (≥2x average)"
            elif snap.volume_ratio >= 1.3:
                snap.volume_status = "elevated"
            elif snap.volume_ratio <= 0.6:
                snap.volume_status = "dry-up (≤0.6x average)"
            else:
                snap.volume_status = "normal"
    obv = compute_obv(df)
    if len(obv) >= 20:
        window = obv.tail(20)
        denom = float(vol.tail(20).mean()) or 1.0
        slope = np.polyfit(range(len(window)), window.values.astype(float), 1)[0]
        snap.obv_slope_20d = float(slope / denom)

    # 52-week structure ---------------------------------------------------------
    year = df.tail(252)
    snap.week52_high = float(year["high"].max())
    snap.week52_low = float(year["low"].min())
    if snap.week52_high:
        snap.pct_from_52w_high = (snap.close / snap.week52_high - 1) * 100
    if snap.week52_low:
        snap.pct_from_52w_low = (snap.close / snap.week52_low - 1) * 100

    # Support / resistance ------------------------------------------------------
    snap.support, snap.resistance = swing_levels(df)
    last = df.iloc[-1]
    pivot = (float(last["high"]) + float(last["low"]) + float(last["close"])) / 3
    snap.pivot = pivot
    snap.pivot_r1 = 2 * pivot - float(last["low"])
    snap.pivot_s1 = 2 * pivot - float(last["high"])

    # Returns -------------------------------------------------------------------
    for days, attr in ((5, "return_5d_pct"), (20, "return_20d_pct"), (60, "return_60d_pct")):
        if len(close) > days and close.iloc[-days - 1]:
            setattr(snap, attr, float((close.iloc[-1] / close.iloc[-days - 1] - 1) * 100))

    snap.trend_score = _trend_score(snap)
    return snap


def _trend_score(snap: TechnicalSnapshot) -> int:
    """0-100 composite trend score used by both the prompt and the rule fallback."""
    score = 50.0

    if snap.is_bullish_stack:
        score += 15
    elif snap.is_bearish_stack:
        score -= 15

    ma50, ma200 = snap.sma.get(50), snap.sma.get(200)
    if ma50 is not None:
        score += 7 if snap.close > ma50 else -7
    if ma200 is not None:
        score += 8 if snap.close > ma200 else -8

    if snap.rsi14 is not None:
        if snap.rsi14 >= 70:
            score += 2          # strong but stretched
        elif snap.rsi14 >= 55:
            score += 8
        elif snap.rsi14 <= 30:
            score -= 4          # weak but potentially washed out
        elif snap.rsi14 <= 45:
            score -= 8

    if snap.macd_hist is not None:
        score += 6 if snap.macd_hist > 0 else -6
    if "bullish" in snap.macd_cross:
        score += 4
    elif "bearish" in snap.macd_cross:
        score -= 4

    if snap.volume_ratio is not None and snap.change_pct is not None:
        if snap.volume_ratio >= 1.3 and snap.change_pct > 0:
            score += 5          # up move confirmed by volume
        elif snap.volume_ratio >= 1.3 and snap.change_pct < 0:
            score -= 5          # heavy selling

    if snap.obv_slope_20d is not None:
        score += 3 if snap.obv_slope_20d > 0 else -3

    return int(max(0, min(100, round(score))))
