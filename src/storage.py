"""SQLite persistence of every analysis run, for history and later backtesting."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from typing import Any, Dict, List

from src.analyzer import AnalysisResult

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analyzed_at TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT,
    price REAL,
    change_pct REAL,
    sentiment_score INTEGER,
    operation_advice TEXT,
    signal_type TEXT,
    analysis_source TEXT,
    payload TEXT
);
CREATE INDEX IF NOT EXISTS idx_history_symbol ON analysis_history(symbol, analyzed_at);
"""


class Storage:
    def __init__(self, path: str):
        self.path = path
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def save_result(self, result: AnalysisResult) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO analysis_history
                        (analyzed_at, symbol, name, price, change_pct, sentiment_score,
                         operation_advice, signal_type, analysis_source, payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result.analyzed_at,
                        result.symbol,
                        result.name,
                        result.price,
                        result.change_pct,
                        result.sentiment_score,
                        result.operation_advice,
                        result.signal_type,
                        result.analysis_source,
                        json.dumps(result.to_dict(), ensure_ascii=False),
                    ),
                )
        except sqlite3.Error as exc:
            logger.warning("failed to persist analysis for %s: %s", result.symbol, exc)

    def latest_results(self) -> List[Dict[str, Any]]:
        """Most recent stored analysis per symbol, best score first (for the web UI)."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload FROM analysis_history a
                WHERE id = (SELECT MAX(id) FROM analysis_history b WHERE b.symbol = a.symbol)
                ORDER BY sentiment_score DESC
                """
            ).fetchall()
        results: List[Dict[str, Any]] = []
        for row in rows:
            try:
                results.append(json.loads(row["payload"]))
            except (json.JSONDecodeError, TypeError):
                continue
        return results

    def recent_for_symbol(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT analyzed_at, symbol, price, change_pct, sentiment_score,
                       operation_advice, signal_type, analysis_source
                FROM analysis_history WHERE symbol = ?
                ORDER BY analyzed_at DESC LIMIT ?
                """,
                (symbol, limit),
            ).fetchall()
        return [dict(row) for row in rows]
