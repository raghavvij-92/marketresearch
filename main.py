#!/usr/bin/env python3
"""
India Stock Researcher — end-to-end daily research pipeline for NSE/BSE.

Pipeline per run:
  1. Parse watchlist (env STOCK_LIST or --stocks)
  2. Build market context (NIFTY/SENSEX/Bank Nifty/India VIX/USDINR/Brent + FII-DII)
  3. Per stock: OHLCV history + fundamentals + NSE extras + news
  4. Compute technical snapshot (MAs, RSI, MACD, Bollinger, ATR, volume, levels)
  5. LLM decision-dashboard analysis (rule-based fallback without a key)
  6. Write markdown reports, persist history to SQLite
  7. Push a digest to Telegram / Discord / Slack / Email

Usage:
  python main.py                              # analyze env watchlist
  python main.py --stocks RELIANCE,TCS        # override watchlist
  python main.py --no-llm                     # rule-based only
  python main.py --no-notify                  # skip notifications
  python main.py --market-only                # market context only
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime

from src.analyzer import StockAnalyzer
from src.config import Config, get_config
from src.data_provider.manager import DataManager
from src.indicators import compute_snapshot
from src.market_context import build_market_context
from src.news import fetch_market_headlines, fetch_stock_news
from src.notification import send_all
from src.report import render_digest, render_notification_text, render_stock_report
from src.storage import Storage
from src.symbols import parse_watchlist

logger = logging.getLogger("main")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="India Stock Researcher (NSE/BSE)")
    parser.add_argument("--stocks", help="comma-separated symbols, overrides STOCK_LIST")
    parser.add_argument("--no-llm", action="store_true", help="skip LLM, rule-based only")
    parser.add_argument("--no-notify", action="store_true", help="skip notifications")
    parser.add_argument("--no-news", action="store_true", help="skip news retrieval")
    parser.add_argument("--market-only", action="store_true", help="only market context")
    parser.add_argument("--output", help="reports directory (default: reports/)")
    return parser.parse_args(argv)


def setup_logging(config: Config) -> None:
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def run(argv=None) -> int:
    args = parse_args(argv)
    config = get_config()
    setup_logging(config)
    if args.no_news:
        config.enable_news = False
    output_dir = args.output or config.output_dir

    tokens = (
        [t.strip() for t in args.stocks.replace(";", ",").split(",") if t.strip()]
        if args.stocks
        else config.stock_list
    )
    watchlist, rejected = parse_watchlist(tokens)
    for bad in rejected:
        logger.warning("ignoring unparseable symbol: %r", bad)
    if not watchlist and not args.market_only:
        logger.error("no valid symbols to analyze (STOCK_LIST=%r)", tokens)
        return 1

    manager = DataManager(config)

    logger.info("building market context...")
    market = build_market_context(config, manager)
    logger.info("market: %s", market.regime_hint)

    headlines = fetch_market_headlines(config) if config.enable_news else []

    if args.market_only:
        print(market.to_prompt_text())
        for item in headlines:
            print(item.to_prompt_line())
        return 0

    analyzer = StockAnalyzer(config)
    use_llm = not args.no_llm
    if use_llm and not analyzer.llm.available:
        logger.warning("no LLM API key configured — falling back to rule-based analysis")
        use_llm = False
    logger.info("analysis engine: %s", analyzer.llm.model_name if use_llm else "rule-based")

    storage = Storage(config.database_path)
    results = []
    date_dir = os.path.join(output_dir, datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(date_dir, exist_ok=True)

    for i, symbol in enumerate(watchlist, 1):
        logger.info("[%d/%d] %s — fetching data", i, len(watchlist), symbol.display)
        stock = manager.fetch_stock(symbol)
        if not stock.ok:
            logger.error(
                "skipping %s: insufficient data (%s)", symbol.symbol, "; ".join(stock.errors)
            )
            continue
        snap = compute_snapshot(stock.bars)
        news = fetch_stock_news(stock, config)
        logger.info(
            "[%d/%d] %s — %d bars, %d news items, trend score %d; analyzing",
            i, len(watchlist), symbol.symbol, len(stock.bars), len(news), snap.trend_score,
        )
        result = analyzer.analyze(stock, snap, news, market, use_llm=use_llm)
        results.append(result)
        storage.save_result(result)

        path = os.path.join(date_dir, f"{symbol.symbol}.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(render_stock_report(result))
        logger.info(
            "[%d/%d] %s — %s (%d/100), report: %s",
            i, len(watchlist), symbol.symbol, result.operation_advice,
            result.sentiment_score, path,
        )

    if not results:
        logger.error("no stocks produced a result — aborting")
        return 1

    digest = render_digest(results, market, headlines)
    digest_path = os.path.join(date_dir, "digest.md")
    with open(digest_path, "w", encoding="utf-8") as fh:
        fh.write(digest)
    latest_path = os.path.join(output_dir, "latest.md")
    with open(latest_path, "w", encoding="utf-8") as fh:
        fh.write(digest)
    logger.info("digest written: %s", digest_path)

    if not args.no_notify:
        if config.has_any_notifier():
            text = render_notification_text(results, market)
            delivered = send_all(config, text)
            logger.info("notifications delivered via: %s", ", ".join(delivered) or "none")
        else:
            logger.info("no notification channel configured — skipping push")

    print(f"\nAnalyzed {len(results)} stock(s). Digest: {digest_path}\n")
    for r in sorted(results, key=lambda x: -x.sentiment_score):
        print(f"  {r.signal_type.split()[0]} {r.symbol:<12} {r.sentiment_score:>3}/100  {r.operation_advice}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
