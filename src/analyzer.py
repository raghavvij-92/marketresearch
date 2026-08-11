"""
AI analysis layer — turns raw data (technicals + fundamentals + news + market
context) into a structured "decision dashboard" for each stock.

The dashboard schema is adapted from ZhuLinsen/daily_stock_analysis for the
Indian market: ₹ price levels, NSE/BSE conventions, circuit limits, delivery
percentage, FII/DII regime, SEBI market-cap buckets.

When no LLM key is configured (or the call fails) a deterministic rule-based
analysis is produced from the same technical snapshot, so the pipeline always
yields a usable report.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.config import Config
from src.data_provider.base import StockData
from src.indicators import TechnicalSnapshot
from src.llm import LLMClient, LLMError
from src.market_context import MarketContext
from src.news import NewsItem

logger = logging.getLogger(__name__)

SIGNAL_BUY = "🟢 BUY signal"
SIGNAL_HOLD = "🟡 HOLD / WATCH"
SIGNAL_SELL = "🔴 SELL signal"
SIGNAL_RISK = "⚠️ RISK ALERT"

SYSTEM_PROMPT = (
    "You are a senior Indian equity research analyst with 15+ years covering "
    "NSE/BSE cash and derivatives markets. You combine technical analysis, "
    "fundamentals, news flow and institutional (FII/DII) positioning into "
    "disciplined, actionable research. You are conservative about risk: you "
    "never chase extended moves, you always define a stop-loss, and you frame "
    "every recommendation for both investors holding the stock and those with "
    "no position. All prices are in Indian Rupees (₹). You respond ONLY with "
    "valid JSON matching the requested schema — no markdown fences, no prose "
    "outside the JSON."
)


@dataclass
class AnalysisResult:
    """Structured output of one stock analysis."""

    symbol: str
    name: str
    price: Optional[float]
    change_pct: Optional[float]
    sentiment_score: int = 50                 # 0 (max bearish) .. 100 (max bullish)
    operation_advice: str = "WATCH"           # BUY / ACCUMULATE / HOLD / REDUCE / SELL / WATCH
    signal_type: str = SIGNAL_HOLD
    analysis_summary: str = ""
    dashboard: Dict[str, Any] = field(default_factory=dict)
    analysis_source: str = "rule-based"       # "llm:<model>" or "rule-based"
    analyzed_at: str = ""
    error: str = ""

    def core_conclusion(self) -> str:
        core = self.dashboard.get("core_conclusion") or {}
        return core.get("one_sentence") or self.analysis_summary or "No conclusion available."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "price": self.price,
            "change_pct": self.change_pct,
            "sentiment_score": self.sentiment_score,
            "operation_advice": self.operation_advice,
            "signal_type": self.signal_type,
            "analysis_summary": self.analysis_summary,
            "dashboard": self.dashboard,
            "analysis_source": self.analysis_source,
            "analyzed_at": self.analyzed_at,
            "error": self.error,
        }


DASHBOARD_SCHEMA = """{
  "sentiment_score": <0-100 integer; 0 = maximum bearish, 100 = maximum bullish>,
  "operation_advice": "<BUY | ACCUMULATE | HOLD | REDUCE | SELL | WATCH>",
  "signal_type": "<🟢 BUY signal | 🟡 HOLD / WATCH | 🔴 SELL signal | ⚠️ RISK ALERT>",
  "analysis_summary": "<~100 word synthesis of the full picture>",
  "dashboard": {
    "core_conclusion": {
      "one_sentence": "<one sentence, max 30 words: exactly what to do and why>",
      "time_sensitivity": "<act immediately | within today's session | this week | no urgency>",
      "position_advice": {
        "no_position": "<specific guidance for someone with no position>",
        "has_position": "<specific guidance for an existing holder>"
      }
    },
    "technical_read": {
      "trend_status": "<moving-average structure and what it implies>",
      "momentum": "<RSI / MACD / stochastic read>",
      "volume_signal": "<volume + delivery % interpretation; in India high delivery % on an up move = conviction buying>",
      "key_levels": {
        "support": <nearest support in ₹ or null>,
        "resistance": <nearest resistance in ₹ or null>
      }
    },
    "fundamental_read": {
      "valuation": "<PE/PB vs sector norms; is the price paying up for growth?>",
      "quality": "<ROE, margins, leverage read>",
      "red_flags": ["<any accounting/governance/leverage concern, or empty list>"]
    },
    "intelligence": {
      "latest_news": "<most material recent news in 1-2 sentences>",
      "risk_alerts": ["<specific risk 1>", "<specific risk 2>"],
      "positive_catalysts": ["<specific catalyst 1>", "<specific catalyst 2>"],
      "sentiment_summary": "<one line on news/flow sentiment>"
    },
    "trade_plan": {
      "entry_zone": "<ideal accumulation zone in ₹, anchored to MA/support>",
      "stop_loss": "<hard stop in ₹ with the technical reason (e.g. below MA20 / swing low)>",
      "target_1": "<first target in ₹ with reasoning>",
      "target_2": "<second target in ₹ or 'trail'>",
      "position_sizing": "<suggested sizing given the setup quality and India VIX regime>",
      "action_checklist": [
        "<✅/⚠️/❌> Moving averages aligned",
        "<✅/⚠️/❌> Momentum supportive",
        "<✅/⚠️/❌> Volume/delivery confirming",
        "<✅/⚠️/❌> No major negative news",
        "<✅/⚠️/❌> Valuation reasonable",
        "<✅/⚠️/❌> Market regime (NIFTY/VIX/FII flows) supportive"
      ]
    },
    "signal_attribution": {
      "technical_indicators": <0-100 contribution weight>,
      "news_sentiment": <0-100>,
      "fundamentals": <0-100>,
      "market_conditions": <0-100>,
      "strongest_bullish_signal": "<name the single strongest bullish input>",
      "strongest_bearish_signal": "<name the single strongest bearish input>"
    }
  },
  "short_term_outlook": "<1-3 trading day view>",
  "medium_term_outlook": "<1-4 week view>",
  "risk_warning": "<the key thing that invalidates this thesis>"
}"""


# ------------------------------------------------------------------ prompt build


def build_prompt(
    stock: StockData,
    snap: TechnicalSnapshot,
    news: List[NewsItem],
    market: Optional[MarketContext],
) -> str:
    sections: List[str] = []
    sections.append(
        f"# Research request: {stock.name} ({stock.symbol.symbol}, {stock.symbol.exchange})\n"
        f"Analysis date: {datetime.now().strftime('%Y-%m-%d')} · Prices in ₹ (INR)."
    )

    if market is not None:
        sections.append(market.to_prompt_text())

    sections.append(_price_section(stock, snap))
    sections.append(_technical_section(snap))
    sections.append(_fundamental_section(stock))
    india_extras = _india_section(stock)
    if india_extras:
        sections.append(india_extras)
    sections.append(_news_section(stock, news))

    sections.append(
        "## Analysis discipline\n"
        "- Anchor all price levels to real technical structure (MAs, swing levels, "
        "pivots, round numbers); never invent arbitrary numbers.\n"
        "- Respect the market regime: heavy FII selling or a spiking India VIX "
        "should temper bullish conviction on individual names.\n"
        "- High delivery percentage on an advance indicates genuine investor "
        "accumulation; low delivery suggests intraday speculation.\n"
        "- If the stock is stretched far above MA5/MA20 (high bias), advise "
        "waiting for a pullback instead of chasing.\n"
        "- If data quality is poor or inputs conflict, say so and lower conviction.\n"
        "- This is research, not guaranteed advice; still, be specific and decisive."
    )

    sections.append(
        "## Output format\nRespond with ONLY the following JSON (no code fences):\n"
        + DASHBOARD_SCHEMA
    )
    return "\n\n".join(sections)


def _fmt(value: Optional[float], digits: int = 2, prefix: str = "") -> str:
    if value is None:
        return "n/a"
    return f"{prefix}{value:,.{digits}f}"


def _price_section(stock: StockData, snap: TechnicalSnapshot) -> str:
    q = stock.quote
    lines = ["## Price snapshot"]
    lines.append(
        f"- Last close: {_fmt(q.price, prefix='₹')} ({_fmt(q.change_pct)}% vs prev close), "
        f"as of {q.as_of or 'n/a'}"
    )
    lines.append(
        f"- Day range: {_fmt(q.low, prefix='₹')} – {_fmt(q.high, prefix='₹')}, "
        f"open {_fmt(q.open, prefix='₹')}, volume {_fmt(q.volume, 0)}"
    )
    lines.append(
        f"- 52-week range: {_fmt(q.week52_low, prefix='₹')} – {_fmt(q.week52_high, prefix='₹')} "
        f"(now {_fmt(snap.pct_from_52w_high)}% from high, "
        f"{_fmt(snap.pct_from_52w_low)}% above low)"
    )
    lines.append(
        f"- Returns: 5d {_fmt(snap.return_5d_pct)}%, 20d {_fmt(snap.return_20d_pct)}%, "
        f"60d {_fmt(snap.return_60d_pct)}%"
    )
    return "\n".join(lines)


def _technical_section(snap: TechnicalSnapshot) -> str:
    sma = snap.sma
    lines = ["## Technical indicators (daily)"]
    lines.append(
        f"- Moving averages: MA5 {_fmt(sma.get(5))} | MA10 {_fmt(sma.get(10))} | "
        f"MA20 {_fmt(sma.get(20))} | MA50 {_fmt(sma.get(50))} | MA200 {_fmt(sma.get(200))}"
    )
    lines.append(f"- MA structure: {snap.ma_alignment or 'insufficient history'}")
    lines.append(
        f"- Bias: {_fmt(snap.bias_ma5_pct)}% vs MA5, {_fmt(snap.bias_ma20_pct)}% vs MA20"
    )
    lines.append(f"- RSI(14): {_fmt(snap.rsi14)}")
    macd_line = (
        f"- MACD(12,26,9): {_fmt(snap.macd, 3)} | signal {_fmt(snap.macd_signal, 3)} | "
        f"histogram {_fmt(snap.macd_hist, 3)}"
    )
    if snap.macd_cross:
        macd_line += f" | {snap.macd_cross}"
    lines.append(macd_line)
    lines.append(f"- Stochastic(14,3): %K {_fmt(snap.stoch_k)} / %D {_fmt(snap.stoch_d)}")
    lines.append(
        f"- Bollinger(20,2): {_fmt(snap.bb_lower)} / {_fmt(snap.bb_mid)} / "
        f"{_fmt(snap.bb_upper)} (%B {_fmt(snap.bb_pct_b)})"
    )
    lines.append(f"- ATR(14): {_fmt(snap.atr14)} ({_fmt(snap.atr_pct)}% of price)")
    vol_line = f"- Volume: {_fmt(snap.volume, 0)}, ratio vs 20d avg {_fmt(snap.volume_ratio)}"
    if snap.volume_status:
        vol_line += f" — {snap.volume_status}"
    lines.append(vol_line)
    if snap.obv_slope_20d is not None:
        trend = "accumulation" if snap.obv_slope_20d > 0 else "distribution"
        lines.append(f"- OBV 20d slope: {_fmt(snap.obv_slope_20d, 3)} ({trend})")
    lines.append(
        f"- Swing levels: support {_fmt(snap.support, prefix='₹')}, "
        f"resistance {_fmt(snap.resistance, prefix='₹')}; "
        f"pivot {_fmt(snap.pivot, prefix='₹')} (R1 {_fmt(snap.pivot_r1, prefix='₹')}, "
        f"S1 {_fmt(snap.pivot_s1, prefix='₹')})"
    )
    lines.append(f"- Composite trend score: {snap.trend_score}/100")
    return "\n".join(lines)


def _fundamental_section(stock: StockData) -> str:
    f = stock.fundamentals
    lines = ["## Fundamentals (best effort)"]
    if f.market_cap is not None:
        lines.append(
            f"- Market cap: ₹{f.market_cap / 1e7:,.0f} crore ({f.market_cap_category})"
        )
    lines.append(
        f"- Valuation: trailing PE {_fmt(f.trailing_pe)}, forward PE {_fmt(f.forward_pe)}, "
        f"P/B {_fmt(f.price_to_book)}, EPS (TTM) {_fmt(f.trailing_eps)}"
    )
    lines.append(
        f"- Quality: ROE {_fmt(f.return_on_equity)}%, profit margin {_fmt(f.profit_margin)}%, "
        f"debt/equity {_fmt(f.debt_to_equity)}"
    )
    lines.append(
        f"- Growth (YoY): revenue {_fmt(f.revenue_growth)}%, earnings {_fmt(f.earnings_growth)}%"
    )
    lines.append(
        f"- Dividend yield: {_fmt(f.dividend_yield)}%, beta {_fmt(f.beta)}"
    )
    if f.sector or f.industry:
        lines.append(f"- Sector / industry: {f.sector or 'n/a'} / {f.industry or 'n/a'}")
    return "\n".join(lines)


def _india_section(stock: StockData) -> str:
    n = stock.nse
    lines: List[str] = []
    if n.delivery_pct is not None:
        lines.append(f"- Delivery percentage (latest session): {n.delivery_pct:.1f}%")
    if n.upper_circuit is not None and n.lower_circuit is not None:
        lines.append(
            f"- Price band today: ₹{n.lower_circuit:,.2f} – ₹{n.upper_circuit:,.2f}"
        )
    if n.is_fno is not None:
        lines.append(f"- F&O segment stock: {'yes' if n.is_fno else 'no'}")
    if n.announcements:
        lines.append("- Recent corporate announcements (NSE):")
        for a in n.announcements[:5]:
            lines.append(f"  - [{a.get('date', '')}] {a.get('subject', '')}")
    if not lines:
        return ""
    return "## NSE-specific data\n" + "\n".join(lines)


def _news_section(stock: StockData, news: List[NewsItem]) -> str:
    if not news:
        return "## Recent news\n- No recent news retrieved (treat news sentiment as neutral)."
    lines = ["## Recent news"]
    for item in news:
        lines.append(item.to_prompt_line())
    return "\n".join(lines)


# -------------------------------------------------------------------- LLM parse


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Pull the first JSON object out of an LLM response, tolerating fences/prose."""
    if not text:
        return None
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start = cleaned.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = cleaned[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    # Common LLM slip: trailing commas.
                    try:
                        return json.loads(re.sub(r",\s*([}\]])", r"\1", candidate))
                    except json.JSONDecodeError:
                        return None
    return None


def _clamp_score(value: Any, default: int = 50) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


_VALID_ADVICE = {"BUY", "ACCUMULATE", "HOLD", "REDUCE", "SELL", "WATCH"}


class StockAnalyzer:
    def __init__(self, config: Config):
        self.config = config
        self.llm = LLMClient(config)

    def analyze(
        self,
        stock: StockData,
        snap: TechnicalSnapshot,
        news: List[NewsItem],
        market: Optional[MarketContext] = None,
        use_llm: bool = True,
    ) -> AnalysisResult:
        result: Optional[AnalysisResult] = None
        error = ""
        if use_llm and self.llm.available:
            try:
                prompt = build_prompt(stock, snap, news, market)
                raw = self.llm.generate(prompt, system=SYSTEM_PROMPT)
                result = self._parse_llm_result(stock, raw)
                if result is None:
                    error = "LLM response was not parseable JSON; fell back to rules"
                    logger.warning("%s for %s", error, stock.symbol.symbol)
            except LLMError as exc:
                error = f"LLM failed: {exc}"
                logger.error("%s (%s); falling back to rule-based", error, stock.symbol.symbol)

        if result is None:
            result = rule_based_analysis(stock, snap, news, market)
            result.error = error
        result.analyzed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return result

    def _parse_llm_result(self, stock: StockData, raw: str) -> Optional[AnalysisResult]:
        data = extract_json(raw)
        if not isinstance(data, dict):
            return None
        advice = str(data.get("operation_advice", "WATCH")).strip().upper()
        if advice not in _VALID_ADVICE:
            advice = "WATCH"
        dashboard = data.get("dashboard") if isinstance(data.get("dashboard"), dict) else {}
        # Carry the outlook/risk fields into the dashboard so rendering is uniform.
        for key in ("short_term_outlook", "medium_term_outlook", "risk_warning"):
            if data.get(key) and key not in dashboard:
                dashboard[key] = data[key]
        return AnalysisResult(
            symbol=stock.symbol.symbol,
            name=stock.name,
            price=stock.quote.price,
            change_pct=stock.quote.change_pct,
            sentiment_score=_clamp_score(data.get("sentiment_score")),
            operation_advice=advice,
            signal_type=str(data.get("signal_type") or SIGNAL_HOLD),
            analysis_summary=str(data.get("analysis_summary") or ""),
            dashboard=dashboard,
            analysis_source=f"llm:{self.llm.model_name}",
        )


# ------------------------------------------------------------------- rule based


def rule_based_analysis(
    stock: StockData,
    snap: TechnicalSnapshot,
    news: List[NewsItem],
    market: Optional[MarketContext] = None,
) -> AnalysisResult:
    """Deterministic fallback built from the technical snapshot alone."""
    score = snap.trend_score

    if score >= 70:
        advice, signal = "BUY", SIGNAL_BUY
    elif score >= 60:
        advice, signal = "ACCUMULATE", SIGNAL_BUY
    elif score >= 45:
        advice, signal = "HOLD", SIGNAL_HOLD
    elif score >= 35:
        advice, signal = "REDUCE", SIGNAL_SELL
    else:
        advice, signal = "SELL", SIGNAL_SELL

    # Over-extension guard: don't advise chasing a stretched move.
    stretched = snap.bias_ma5_pct is not None and snap.bias_ma5_pct > 5.0
    if advice in {"BUY", "ACCUMULATE"} and stretched:
        advice, signal = "WATCH", SIGNAL_HOLD

    ma20 = snap.sma.get(20)
    stop = snap.support if snap.support is not None else ma20
    entry = snap.sma.get(5) or snap.close
    target = snap.resistance if snap.resistance is not None else snap.pivot_r1

    checklist = [
        f"{'✅' if snap.is_bullish_stack else ('❌' if snap.is_bearish_stack else '⚠️')} "
        "Moving averages aligned",
        f"{'✅' if (snap.rsi14 or 50) >= 50 and (snap.macd_hist or 0) > 0 else '⚠️'} "
        "Momentum supportive",
        f"{'✅' if (snap.volume_ratio or 1) >= 1.0 else '⚠️'} Volume confirming",
        "⚠️ News not machine-assessed (rule-based mode)",
        "⚠️ Valuation not machine-assessed (rule-based mode)",
    ]
    if market is not None:
        nifty = market.get("NIFTY 50")
        supportive = nifty is not None and (nifty.return_5d_pct or 0) >= 0
        checklist.append(f"{'✅' if supportive else '⚠️'} Market regime supportive")

    summary = (
        f"Rule-based technical read: trend score {score}/100, {snap.ma_alignment or 'n/a'}, "
        f"RSI {snap.rsi14:.0f}" if snap.rsi14 is not None else
        f"Rule-based technical read: trend score {score}/100"
    )

    dashboard: Dict[str, Any] = {
        "core_conclusion": {
            "one_sentence": _rule_sentence(stock, snap, advice, stretched),
            "time_sensitivity": "no urgency",
            "position_advice": {
                "no_position": (
                    "Wait for a pullback toward MA5/support before entering"
                    if stretched
                    else f"Consider staged entry near ₹{entry:,.2f}"
                    if advice in {"BUY", "ACCUMULATE"}
                    else "Stay on the sidelines until the trend improves"
                ),
                "has_position": (
                    f"Hold with a stop below ₹{stop:,.2f}"
                    if stop is not None and advice not in {"SELL", "REDUCE"}
                    else "Consider reducing exposure into strength"
                ),
            },
        },
        "technical_read": {
            "trend_status": snap.ma_alignment or "insufficient history",
            "momentum": (
                f"RSI(14) {snap.rsi14:.1f}, MACD histogram "
                f"{'positive' if (snap.macd_hist or 0) > 0 else 'negative'}"
                if snap.rsi14 is not None
                else "insufficient history"
            ),
            "volume_signal": snap.volume_status or "n/a",
            "key_levels": {"support": snap.support, "resistance": snap.resistance},
        },
        "intelligence": {
            "latest_news": news[0].title if news else "No recent news retrieved.",
            "risk_alerts": [],
            "positive_catalysts": [],
            "sentiment_summary": "News sentiment not assessed in rule-based mode.",
        },
        "trade_plan": {
            "entry_zone": f"near ₹{entry:,.2f} (MA5)" if entry else "n/a",
            "stop_loss": f"₹{stop:,.2f} (swing support / MA20)" if stop is not None else "n/a",
            "target_1": f"₹{target:,.2f} (nearest resistance)" if target is not None else "n/a",
            "target_2": "trail using MA10",
            "position_sizing": "Standard sizing only; this is a rule-based read without news/fundamental confirmation.",
            "action_checklist": checklist,
        },
        "signal_attribution": {
            "technical_indicators": 100,
            "news_sentiment": 0,
            "fundamentals": 0,
            "market_conditions": 0,
            "strongest_bullish_signal": "bullish MA stack" if snap.is_bullish_stack else "trend score",
            "strongest_bearish_signal": "bearish MA stack" if snap.is_bearish_stack else "trend score",
        },
        "risk_warning": (
            "Rule-based output uses technicals only — verify news and fundamentals "
            "before acting. A close below the stop level invalidates the setup."
        ),
    }

    return AnalysisResult(
        symbol=stock.symbol.symbol,
        name=stock.name,
        price=stock.quote.price,
        change_pct=stock.quote.change_pct,
        sentiment_score=score,
        operation_advice=advice,
        signal_type=signal,
        analysis_summary=summary,
        dashboard=dashboard,
        analysis_source="rule-based",
    )


def _rule_sentence(stock: StockData, snap: TechnicalSnapshot, advice: str, stretched: bool) -> str:
    name = stock.symbol.symbol
    if stretched:
        return f"{name} is extended above its short-term averages — wait for a pullback."
    verb = {
        "BUY": "shows a bullish technical setup",
        "ACCUMULATE": "is building a constructive technical base",
        "HOLD": "is in a neutral technical zone — hold existing positions",
        "REDUCE": "is losing technical momentum — consider trimming",
        "SELL": "is in a technical downtrend — avoid fresh exposure",
        "WATCH": "needs confirmation before any action",
    }[advice]
    return f"{name} {verb} (trend score {snap.trend_score}/100)."
