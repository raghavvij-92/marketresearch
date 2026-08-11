from src.analyzer import rule_based_analysis
from src.indicators import compute_snapshot
from src.notification.base import chunk_text
from src.report import render_digest, render_notification_text, render_stock_report
from src.storage import Storage


def _result(stock_data):
    snap = compute_snapshot(stock_data.bars)
    result = rule_based_analysis(stock_data, snap, [])
    result.analyzed_at = "2026-08-11 18:00:00"
    return result


def test_stock_report_renders(stock_data):
    md = render_stock_report(_result(stock_data))
    assert "RELIANCE" in md
    assert "Core conclusion" in md
    assert "Trade plan" in md
    assert "Disclaimer" in md
    assert "₹" in md


def test_digest_renders_table(stock_data):
    md = render_digest([_result(stock_data)], None, [])
    assert "| Stock |" in md
    assert "RELIANCE" in md


def test_notification_text_compact(stock_data):
    text = render_notification_text([_result(stock_data)], None)
    assert "RELIANCE" in text
    assert "not investment advice" in text


def test_chunk_text_respects_limit():
    text = "\n".join(f"line {i} " + "x" * 50 for i in range(200))
    chunks = chunk_text(text, 500)
    assert all(len(c) <= 500 for c in chunks)
    assert "\n".join(chunks).replace("\n", "") == text.replace("\n", "")


def test_chunk_text_short_passthrough():
    assert chunk_text("hello", 100) == ["hello"]


def test_storage_roundtrip(stock_data, tmp_path):
    storage = Storage(str(tmp_path / "test.db"))
    result = _result(stock_data)
    storage.save_result(result)
    rows = storage.recent_for_symbol("RELIANCE")
    assert len(rows) == 1
    assert rows[0]["symbol"] == "RELIANCE"
    assert rows[0]["operation_advice"] == result.operation_advice
