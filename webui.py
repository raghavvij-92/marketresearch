#!/usr/bin/env python3
"""
Local web dashboard for the India Stock Researcher.

Zero extra dependencies — stdlib http.server only.

    python webui.py                 # http://127.0.0.1:8000
    python webui.py --port 9000
    python webui.py --host 0.0.0.0  # expose on your LAN

Features:
  * dashboard of the latest analysis per stock (from the SQLite history)
  * live market context (indices, India VIX, FII/DII), refreshed in background
  * "Run analysis" button — kicks off the full pipeline in a worker thread,
    streams log lines to the page, reloads when finished
"""

from __future__ import annotations

import argparse
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import List, Optional

from src.config import get_config
from src.data_provider.manager import DataManager
from src.market_context import MarketContext, build_market_context
from src.storage import Storage
from src.webpage import render_dashboard

logger = logging.getLogger("webui")


class AppState:
    """Shared state between HTTP threads and the pipeline worker."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.status = "idle"                # idle | running
        self.log: List[str] = []
        self.market: Optional[MarketContext] = None

    def log_line(self, line: str) -> None:
        with self.lock:
            self.log.append(line)
            self.log = self.log[-200:]

    def snapshot(self) -> dict:
        with self.lock:
            return {"status": self.status, "log": list(self.log)}


STATE = AppState()


class _StateLogHandler(logging.Handler):
    """Mirror pipeline log records into the web UI's run log."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            STATE.log_line(self.format(record))
        except Exception:
            pass


def _refresh_market() -> None:
    config = get_config()
    try:
        market = build_market_context(config, DataManager(config))
        with STATE.lock:
            STATE.market = market
        STATE.log_line(f"market context refreshed: {market.regime_hint}")
    except Exception as exc:
        STATE.log_line(f"market context refresh failed: {exc}")


def _run_pipeline(stocks: str, no_llm: bool) -> None:
    import main as pipeline

    handler = _StateLogHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))
    logging.getLogger().addHandler(handler)
    try:
        argv = ["--no-notify"]
        if stocks.strip():
            argv += ["--stocks", stocks.strip()]
        if no_llm:
            argv.append("--no-llm")
        STATE.log_line(f"starting pipeline: {' '.join(argv)}")
        code = pipeline.run(argv)
        STATE.log_line(f"pipeline finished with exit code {code}")
    except Exception as exc:
        STATE.log_line(f"pipeline crashed: {exc}")
    finally:
        logging.getLogger().removeHandler(handler)
        _refresh_market()
        with STATE.lock:
            STATE.status = "idle"


class Handler(BaseHTTPRequestHandler):
    server_version = "IndiaStockResearcher/1.0"

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict, code: int = 200) -> None:
        self._send(code, json.dumps(payload).encode("utf-8"), "application/json")

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        if self.path in ("/", "/index.html"):
            config = get_config()
            results = Storage(config.database_path).latest_results()
            with STATE.lock:
                market = STATE.market
            page = render_dashboard(
                results,
                market,
                with_controls=True,
                stock_list=",".join(config.stock_list),
            )
            self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/api/status":
            self._send_json(STATE.snapshot())
        elif self.path == "/api/results":
            config = get_config()
            self._send_json({"results": Storage(config.database_path).latest_results()})
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/run":
            self._send_json({"error": "not found"}, 404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            body = {}
        with STATE.lock:
            if STATE.status == "running":
                self._send_json({"status": "running", "note": "a run is already in progress"})
                return
            STATE.status = "running"
            STATE.log = []
        thread = threading.Thread(
            target=_run_pipeline,
            args=(str(body.get("stocks") or ""), bool(body.get("no_llm"))),
            daemon=True,
        )
        thread.start()
        self._send_json({"status": "running"})

    def log_message(self, fmt: str, *args) -> None:  # quiet default access logging
        logger.debug(fmt, *args)


def main() -> None:
    parser = argparse.ArgumentParser(description="India Stock Researcher web dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S")

    # Warm the market context in the background so the first page load is fast.
    threading.Thread(target=_refresh_market, daemon=True).start()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"\n  India Stock Researcher dashboard → http://{args.host}:{args.port}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
