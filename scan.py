#!/usr/bin/env python3
"""
Short-term opportunity scanner.

Sweeps a universe of liquid NSE names, computes the full technical snapshot
for each, classifies short-horizon setups, and ranks them. This is a
technical screen, not a recommendation engine — every candidate needs your
own diligence on news and fundamentals before any trade.

Setup types detected (1-5 trading day horizon):
  breakout   — closing within 2% of swing resistance / 52-week high on
               healthy momentum: watch for a volume breakout
  momentum   — bullish MA stack, RSI 55-75, positive MACD, not extended:
               trend continuation candidates
  pullback   — established uptrend (price > MA50 > MA200) resting near
               MA20/support with cooled RSI: buy-the-dip zone
  oversold   — RSI < 32 washouts above long-term support: speculative
               mean-reversion bounces (highest risk)

Usage:
  python scan.py                          # scan NIFTY100, top 12
  python scan.py --top 20 --min-score 55
  python scan.py --deep                   # run full analysis on the top 5
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from src.config import get_config
from src.data_provider import yahoo_fetcher
from src.indicators import TechnicalSnapshot, compute_snapshot
from src.symbols import parse_symbol
from src.universe import UNIVERSES

logger = logging.getLogger("scan")


@dataclass
class Candidate:
    symbol: str
    setup: str
    rank_score: float
    snap: TechnicalSnapshot

    @property
    def _atr(self) -> float:
        return self.snap.atr14 or self.snap.close * 0.02

    @property
    def entry(self) -> Optional[float]:
        return self.snap.sma.get(5) or self.snap.close

    @property
    def stop(self) -> Optional[float]:
        """Tightest sensible floor below price: swing support, MA20 or 2 ATR."""
        close = self.snap.close
        floors = [
            level
            for level in (self.snap.support, self.snap.sma.get(20), close - 2 * self._atr)
            if level is not None and level < close
        ]
        return max(floors) if floors else None

    @property
    def target(self) -> Optional[float]:
        """Overhead resistance when it's meaningfully above; else a 2-ATR measured move."""
        close = self.snap.close
        resistance = self.snap.resistance
        if self.setup == "breakout":
            base = resistance if resistance is not None and resistance > close else close
            return base + 2 * self._atr
        if resistance is not None and resistance > close * 1.01:
            return resistance
        return close + 2 * self._atr

    @property
    def risk_reward(self) -> Optional[float]:
        if self.stop is None or self.target is None or self.snap.close <= self.stop:
            return None
        risk = self.snap.close - self.stop
        reward = self.target - self.snap.close
        if risk <= 0 or reward <= 0:
            return None
        return reward / risk


def classify(snap: TechnicalSnapshot) -> Optional[Candidate]:
    """Return a Candidate when the snapshot matches a short-term setup."""
    if snap.close <= 0 or snap.rsi14 is None:
        return None

    rsi = snap.rsi14
    bias5 = snap.bias_ma5_pct or 0.0
    vol_ratio = snap.volume_ratio or 1.0
    macd_pos = (snap.macd_hist or 0) > 0
    above_ma50 = snap.sma.get(50) is not None and snap.close > snap.sma[50]
    above_ma200 = snap.sma.get(200) is not None and snap.close > snap.sma[200]

    near_resistance = (
        snap.resistance is not None and snap.close >= snap.resistance * 0.98
    )
    near_52w_high = (
        snap.pct_from_52w_high is not None and snap.pct_from_52w_high > -3.0
    )

    # Breakout watch: knocking on the door with momentum behind it.
    if (near_resistance or near_52w_high) and macd_pos and rsi >= 55 and bias5 <= 6:
        score = snap.trend_score + 8 + min(vol_ratio, 2.0) * 3
        return Candidate("", "breakout", score, snap)

    # Momentum continuation: healthy trend, not stretched.
    if snap.is_bullish_stack and 55 <= rsi <= 75 and macd_pos and bias5 <= 4:
        score = snap.trend_score + 5 + min(vol_ratio, 2.0) * 2
        return Candidate("", "momentum", score, snap)

    # Pullback in an uptrend: resting on the 20-day / support.
    ma20 = snap.sma.get(20)
    near_ma20 = ma20 is not None and abs(snap.close / ma20 - 1) <= 0.015
    if above_ma50 and above_ma200 and 40 <= rsi <= 55 and near_ma20:
        return Candidate("", "pullback", snap.trend_score + 4, snap)

    # Oversold washout: speculative bounce candidates only.
    if rsi < 32 and above_ma200:
        return Candidate("", "oversold", max(20.0, 100 - snap.trend_score) * 0.55, snap)

    return None


def scan_universe(names: List[str], min_score: float, workers: int = 6) -> List[Candidate]:
    config = get_config()
    candidates: List[Candidate] = []

    def fetch_one(name: str) -> Optional[Candidate]:
        try:
            sym = parse_symbol(name)
            bars = yahoo_fetcher.fetch_daily_bars(sym, days=config.history_days)
            if bars is None or len(bars) < 60:
                return None
            cand = classify(compute_snapshot(bars))
            if cand is not None:
                cand.symbol = sym.symbol
            return cand
        except Exception as exc:
            logger.debug("scan failed for %s: %s", name, exc)
            return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_one, n): n for n in names}
        done = 0
        for future in as_completed(futures):
            done += 1
            if done % 20 == 0:
                logger.info("scanned %d/%d", done, len(futures))
            cand = future.result()
            if cand is not None and cand.rank_score >= min_score:
                candidates.append(cand)

    candidates.sort(key=lambda c: -c.rank_score)
    return candidates


def _fmt(value: Optional[float], prefix: str = "") -> str:
    return "n/a" if value is None else f"{prefix}{value:,.2f}"


def render_scan_report(candidates: List[Candidate], universe: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# 🔍 Short-term setup scan — {today}",
        "",
        f"Universe: {universe} · horizon: 1-5 trading days · technicals only.",
        "",
        "| # | Stock | Setup | Score | Close | RSI | Vol× | Entry zone | Stop | Target | R:R |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, c in enumerate(candidates, 1):
        rr = f"{c.risk_reward:.1f}" if c.risk_reward is not None else "n/a"
        lines.append(
            f"| {i} | **{c.symbol}** | {c.setup} | {c.rank_score:.0f} | "
            f"{_fmt(c.snap.close, '₹')} | {c.snap.rsi14:.0f} | "
            f"{(c.snap.volume_ratio or 0):.1f} | {_fmt(c.entry, '₹')} | "
            f"{_fmt(c.stop, '₹')} | {_fmt(c.target, '₹')} | {rr} |"
        )
    lines += [
        "",
        "Setup legend: **breakout** = near resistance/52-week high with momentum; "
        "**momentum** = bullish stack, healthy RSI, not extended; "
        "**pullback** = uptrend resting at MA20/support; "
        "**oversold** = speculative RSI washout bounce (highest risk).",
        "",
        "> ⚠️ Technical screen only — verify news, results calendar and liquidity "
        "before any trade. Not investment advice; the author is not a "
        "SEBI-registered adviser. Short-term trading carries elevated risk.",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Short-term NSE setup scanner")
    parser.add_argument("--universe", default="nifty100", choices=sorted(UNIVERSES))
    parser.add_argument("--top", type=int, default=12)
    parser.add_argument("--min-score", type=float, default=50.0)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--deep", action="store_true", help="run full analysis on the top 5")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")

    names = UNIVERSES[args.universe]
    logger.info("scanning %d names in %s...", len(names), args.universe)
    candidates = scan_universe(names, args.min_score, args.workers)[: args.top]

    report = render_scan_report(candidates, args.universe)
    config = get_config()
    os.makedirs(config.output_dir, exist_ok=True)
    path = os.path.join(config.output_dir, f"scan-{datetime.now().strftime('%Y-%m-%d')}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(report)

    print()
    print(report)
    print(f"\nreport written: {path}")

    if args.deep and candidates:
        from main import run as run_pipeline

        top = ",".join(c.symbol for c in candidates[:5])
        logger.info("running deep analysis on: %s", top)
        run_pipeline(["--stocks", top, "--no-notify"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
