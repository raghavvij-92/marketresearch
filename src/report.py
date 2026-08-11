"""
Report rendering: full markdown research notes per stock, a daily digest that
opens with the market context, and a compact text used for notifications.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from src.analyzer import AnalysisResult
from src.market_context import MarketContext
from src.news import NewsItem

DISCLAIMER = (
    "> ⚠️ **Disclaimer**: This report is generated automatically for research and "
    "educational purposes only. It is **not** investment advice and the author is "
    "not a SEBI-registered investment adviser. Markets involve risk; do your own "
    "diligence or consult a registered adviser before acting."
)


def _fmt(value: Optional[float], digits: int = 2, prefix: str = "") -> str:
    if value is None:
        return "n/a"
    try:
        return f"{prefix}{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _section(dashboard: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = dashboard.get(key)
    return value if isinstance(value, dict) else {}


def _listify(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if value:
        return [str(value)]
    return []


def render_stock_report(result: AnalysisResult) -> str:
    """Full markdown research note for one stock."""
    d = result.dashboard
    core = _section(d, "core_conclusion")
    tech = _section(d, "technical_read")
    fund = _section(d, "fundamental_read")
    intel = _section(d, "intelligence")
    plan = _section(d, "trade_plan")
    attr = _section(d, "signal_attribution")

    lines: List[str] = []
    change = f" ({result.change_pct:+.2f}%)" if result.change_pct is not None else ""
    lines.append(f"# {result.name} ({result.symbol}) — {result.signal_type}")
    lines.append("")
    lines.append(
        f"**Price**: {_fmt(result.price, prefix='₹')}{change} · "
        f"**Score**: {result.sentiment_score}/100 · "
        f"**Advice**: {result.operation_advice} · "
        f"**Engine**: {result.analysis_source} · {result.analyzed_at}"
    )
    lines.append("")
    lines.append(f"## 🎯 Core conclusion\n\n**{result.core_conclusion()}**")
    if core.get("time_sensitivity"):
        lines.append(f"\n- **Urgency**: {core['time_sensitivity']}")
    pos = _section(core, "position_advice")
    if pos.get("no_position"):
        lines.append(f"- **If you hold nothing**: {pos['no_position']}")
    if pos.get("has_position"):
        lines.append(f"- **If you hold the stock**: {pos['has_position']}")

    if tech:
        lines.append("\n## 📊 Technical read")
        for label, key in (
            ("Trend", "trend_status"),
            ("Momentum", "momentum"),
            ("Volume / delivery", "volume_signal"),
        ):
            if tech.get(key):
                lines.append(f"- **{label}**: {tech[key]}")
        levels = _section(tech, "key_levels")
        if levels:
            lines.append(
                f"- **Key levels**: support {_fmt(levels.get('support'), prefix='₹')} · "
                f"resistance {_fmt(levels.get('resistance'), prefix='₹')}"
            )

    if fund:
        lines.append("\n## 🏛️ Fundamental read")
        for label, key in (("Valuation", "valuation"), ("Quality", "quality")):
            if fund.get(key):
                lines.append(f"- **{label}**: {fund[key]}")
        red_flags = _listify(fund.get("red_flags"))
        if red_flags:
            lines.append("- **Red flags**: " + "; ".join(red_flags))

    if intel:
        lines.append("\n## 📰 Intelligence")
        if intel.get("latest_news"):
            lines.append(f"- **Latest news**: {intel['latest_news']}")
        for risk in _listify(intel.get("risk_alerts")):
            lines.append(f"- 🔻 {risk}")
        for cat in _listify(intel.get("positive_catalysts")):
            lines.append(f"- 🔺 {cat}")
        if intel.get("sentiment_summary"):
            lines.append(f"- **Sentiment**: {intel['sentiment_summary']}")

    if plan:
        lines.append("\n## 🗡️ Trade plan")
        for label, key in (
            ("Entry zone", "entry_zone"),
            ("Stop loss", "stop_loss"),
            ("Target 1", "target_1"),
            ("Target 2", "target_2"),
            ("Position sizing", "position_sizing"),
        ):
            if plan.get(key):
                lines.append(f"- **{label}**: {plan[key]}")
        checklist = _listify(plan.get("action_checklist"))
        if checklist:
            lines.append("\n**Checklist**")
            for item in checklist:
                lines.append(f"- {item}")

    for label, key in (
        ("⏱️ Short-term outlook (1-3 days)", "short_term_outlook"),
        ("📅 Medium-term outlook (1-4 weeks)", "medium_term_outlook"),
        ("⚠️ Risk warning", "risk_warning"),
    ):
        if d.get(key):
            lines.append(f"\n## {label}\n\n{d[key]}")

    if attr:
        lines.append("\n## 🧭 Signal attribution")
        weights = []
        for label, key in (
            ("Technicals", "technical_indicators"),
            ("News", "news_sentiment"),
            ("Fundamentals", "fundamentals"),
            ("Market", "market_conditions"),
        ):
            if attr.get(key) is not None:
                weights.append(f"{label} {attr[key]}")
        if weights:
            lines.append("- **Weights**: " + " · ".join(weights))
        if attr.get("strongest_bullish_signal"):
            lines.append(f"- **Strongest bullish**: {attr['strongest_bullish_signal']}")
        if attr.get("strongest_bearish_signal"):
            lines.append(f"- **Strongest bearish**: {attr['strongest_bearish_signal']}")

    if result.analysis_summary:
        lines.append(f"\n## 📝 Summary\n\n{result.analysis_summary}")
    if result.error:
        lines.append(f"\n> ⚠️ Note: {result.error}")

    lines.append("\n---\n" + DISCLAIMER)
    return "\n".join(lines)


def render_digest(
    results: List[AnalysisResult],
    market: Optional[MarketContext],
    headlines: Optional[List[NewsItem]] = None,
) -> str:
    """Daily digest: market context + one-line summary per stock + full notes."""
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"# 🇮🇳 India Stock Research — {today}", ""]

    if market is not None:
        lines.append(market.to_prompt_text().replace("## Indian Market Context", "## 🌐 Market context"))
        lines.append("")

    if headlines:
        lines.append("## 🗞️ Market headlines")
        for item in headlines[:8]:
            lines.append(item.to_prompt_line())
        lines.append("")

    lines.append("## 📋 Watchlist summary")
    lines.append("")
    lines.append("| Stock | Price | Chg % | Score | Signal | Advice |")
    lines.append("|---|---|---|---|---|---|")
    for r in sorted(results, key=lambda x: -x.sentiment_score):
        chg = f"{r.change_pct:+.2f}%" if r.change_pct is not None else "n/a"
        lines.append(
            f"| {r.symbol} | {_fmt(r.price, prefix='₹')} | {chg} | "
            f"{r.sentiment_score} | {r.signal_type} | {r.operation_advice} |"
        )
    lines.append("")

    for r in sorted(results, key=lambda x: -x.sentiment_score):
        lines.append("---")
        lines.append("")
        lines.append(render_stock_report(r))
        lines.append("")
    return "\n".join(lines)


def render_notification_text(
    results: List[AnalysisResult], market: Optional[MarketContext]
) -> str:
    """Compact plain-text summary suitable for chat notifications."""
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"🇮🇳 India Stock Research — {today}", ""]
    if market is not None:
        lines.append(f"🌐 {market.regime_hint}")
        lines.append("")
    for r in sorted(results, key=lambda x: -x.sentiment_score):
        chg = f" {r.change_pct:+.2f}%" if r.change_pct is not None else ""
        lines.append(
            f"{r.signal_type.split()[0]} {r.symbol} {_fmt(r.price, prefix='₹')}{chg} · "
            f"{r.sentiment_score}/100 · {r.operation_advice}"
        )
        lines.append(f"   {r.core_conclusion()}")
    lines.append("")
    lines.append("⚠️ Automated research, not investment advice.")
    return "\n".join(lines)
