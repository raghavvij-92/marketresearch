import json

from src.analyzer import (
    SIGNAL_BUY,
    SIGNAL_HOLD,
    build_prompt,
    extract_json,
    rule_based_analysis,
)
from src.indicators import compute_snapshot


def test_extract_json_plain():
    data = extract_json('{"a": 1, "b": {"c": [1, 2]}}')
    assert data == {"a": 1, "b": {"c": [1, 2]}}


def test_extract_json_with_fences_and_prose():
    text = 'Here is my analysis:\n```json\n{"sentiment_score": 72}\n```\nHope it helps!'
    assert extract_json(text) == {"sentiment_score": 72}


def test_extract_json_trailing_comma():
    assert extract_json('{"a": 1,}') == {"a": 1}


def test_extract_json_braces_inside_strings():
    payload = {"note": 'contains "{" and "}" chars'}
    assert extract_json(json.dumps(payload)) == payload


def test_extract_json_garbage():
    assert extract_json("no json here") is None
    assert extract_json("") is None


def test_build_prompt_contains_key_sections(stock_data):
    snap = compute_snapshot(stock_data.bars)
    prompt = build_prompt(stock_data, snap, [], None)
    for expected in (
        "RELIANCE",
        "Technical indicators",
        "Fundamentals",
        "Output format",
        "sentiment_score",
        "trade_plan",
        "₹",
    ):
        assert expected in prompt


def test_rule_based_uptrend_is_constructive(stock_data):
    snap = compute_snapshot(stock_data.bars)
    result = rule_based_analysis(stock_data, snap, [])
    assert result.symbol == "RELIANCE"
    assert result.analysis_source == "rule-based"
    assert 0 <= result.sentiment_score <= 100
    assert result.operation_advice in {"BUY", "ACCUMULATE", "HOLD", "REDUCE", "SELL", "WATCH"}
    assert result.dashboard["core_conclusion"]["one_sentence"]
    assert result.dashboard["trade_plan"]["action_checklist"]


def test_rule_based_overextension_guard(stock_data):
    snap = compute_snapshot(stock_data.bars)
    snap.trend_score = 80
    snap.bias_ma5_pct = 9.0  # heavily stretched above MA5
    result = rule_based_analysis(stock_data, snap, [])
    assert result.operation_advice == "WATCH"
    assert result.signal_type == SIGNAL_HOLD
    assert "pullback" in result.dashboard["core_conclusion"]["one_sentence"].lower()


def test_rule_based_strong_uptrend_buy(stock_data):
    snap = compute_snapshot(stock_data.bars)
    snap.trend_score = 75
    snap.bias_ma5_pct = 1.0
    result = rule_based_analysis(stock_data, snap, [])
    assert result.operation_advice == "BUY"
    assert result.signal_type == SIGNAL_BUY
