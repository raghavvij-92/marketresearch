from src.analyzer import rule_based_analysis
from src.indicators import compute_snapshot
from src.webpage import render_dashboard


def _payload(stock_data):
    snap = compute_snapshot(stock_data.bars)
    result = rule_based_analysis(stock_data, snap, [])
    result.analyzed_at = "2026-08-11 18:00:00"
    return result.to_dict()


def test_dashboard_renders_with_results(stock_data):
    html = render_dashboard([_payload(stock_data)], None, with_controls=True)
    assert "<!doctype html>" in html
    assert "RELIANCE" in html
    assert "Run analysis" in html
    assert "Disclaimer" in html
    assert 'id="runform"' in html


def test_dashboard_renders_empty_state():
    html = render_dashboard([], None, with_controls=False)
    assert "No analyses yet" in html
    assert 'id="runform"' not in html


def test_dashboard_escapes_content(stock_data):
    payload = _payload(stock_data)
    payload["name"] = '<script>alert("x")</script>'
    html = render_dashboard([payload], None)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
