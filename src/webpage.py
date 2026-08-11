"""
HTML rendering for the web dashboard (used by webui.py).

Turns stored analysis payloads + market context into a self-contained page:
no external assets, light/dark aware, works from `python webui.py`.
"""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.market_context import MarketContext

_e = html.escape

_CSS = """
:root {
  --bg:#FAFBF9; --surface:#FFFFFF; --ink:#1C2422; --muted:#5C6B64;
  --line:#DCE4DF; --accent:#0E6B5C; --accent-ink:#FFFFFF;
  --good:#1E7F3C; --bad:#BA3A2B; --warn:#A87A12;
  --good-bg:#E7F2E9; --bad-bg:#F7E9E6; --warn-bg:#F5EEDB; --hold-bg:#EDF1EE;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg:#101614; --surface:#18201D; --ink:#E6ECE9; --muted:#93A39B;
    --line:#2A3530; --accent:#45B598; --accent-ink:#0E1512;
    --good:#5CBF7A; --bad:#E0796A; --warn:#D3A945;
    --good-bg:#1B2B20; --bad-bg:#30201C; --warn-bg:#2D2718; --hold-bg:#1E2723;
  }
}
:root[data-theme="dark"] {
  --bg:#101614; --surface:#18201D; --ink:#E6ECE9; --muted:#93A39B;
  --line:#2A3530; --accent:#45B598; --accent-ink:#0E1512;
  --good:#5CBF7A; --bad:#E0796A; --warn:#D3A945;
  --good-bg:#1B2B20; --bad-bg:#30201C; --warn-bg:#2D2718; --hold-bg:#1E2723;
}
* { box-sizing:border-box; }
body { background:var(--bg); color:var(--ink); margin:0;
  font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }
.wrap { max-width:60rem; margin:0 auto; padding:2rem 1.25rem 4rem; }
.num { font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace; font-variant-numeric:tabular-nums; font-size:.95em; }
.muted { color:var(--muted); }
.up { color:var(--good); } .down { color:var(--bad); }
a { color:var(--accent); }
a:focus-visible, button:focus-visible, input:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
.masthead { border-bottom:3px double var(--line); padding-bottom:1.25rem; margin-bottom:1.5rem; }
.masthead h1 { font-family:Georgia,"Times New Roman",serif; font-weight:700;
  font-size:clamp(1.7rem,4vw,2.4rem); margin:0 0 .25rem; text-wrap:balance; }
.masthead .date { text-transform:uppercase; letter-spacing:.08em; font-size:.78rem; color:var(--muted); }
.regime { margin:.75rem 0 0; padding:.6rem .9rem; background:var(--surface);
  border-left:3px solid var(--accent); border-radius:0 4px 4px 0; font-size:.95rem; }
.engine { font-size:.8rem; color:var(--muted); margin-top:.5rem; }
h2 { font-family:Georgia,serif; font-size:1.25rem; margin:2.25rem 0 .9rem;
  padding-bottom:.35rem; border-bottom:1px solid var(--line); }
.controls { display:flex; gap:.6rem; flex-wrap:wrap; align-items:center;
  background:var(--surface); border:1px solid var(--line); border-radius:6px;
  padding:.8rem 1rem; margin-top:1rem; }
.controls input[type=text] { flex:1 1 16rem; padding:.45rem .6rem; border:1px solid var(--line);
  border-radius:4px; background:var(--bg); color:var(--ink); font:inherit; }
.controls label { font-size:.85rem; display:flex; gap:.3rem; align-items:center; }
.controls button { background:var(--accent); color:var(--accent-ink); border:none;
  border-radius:4px; padding:.5rem 1.1rem; font:inherit; font-weight:600; cursor:pointer; }
.controls button[disabled] { opacity:.55; cursor:wait; }
.runlog { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:.78rem; white-space:pre-wrap;
  background:var(--surface); border:1px solid var(--line); border-radius:6px;
  padding:.7rem .9rem; margin-top:.75rem; max-height:14rem; overflow-y:auto; }
.idx-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(13rem,1fr)); gap:.75rem; }
.idx { background:var(--surface); border:1px solid var(--line); border-radius:6px; padding:.7rem .85rem; }
.idx-name { font-size:.72rem; text-transform:uppercase; letter-spacing:.07em; color:var(--muted); }
.idx-level { font-size:1.15rem; font-weight:600; margin:.15rem 0; }
.idx-deltas { display:flex; gap:.6rem; font-size:.8rem; flex-wrap:wrap; }
.flows { margin:.9rem 0 0; font-size:.92rem; }
.table-scroll { overflow-x:auto; border:1px solid var(--line); border-radius:6px; background:var(--surface); }
table { border-collapse:collapse; width:100%; min-width:38rem; font-size:.95rem; }
th { text-align:left; font-size:.72rem; text-transform:uppercase; letter-spacing:.07em;
  color:var(--muted); font-weight:600; padding:.6rem .8rem; border-bottom:1px solid var(--line); }
td { padding:.55rem .8rem; border-bottom:1px solid var(--line); }
tr:last-child td { border-bottom:none; }
.sym { font-weight:600; text-decoration:none; }
.pill { display:inline-block; padding:.15rem .6rem; border-radius:999px; font-size:.78rem; font-weight:600; white-space:nowrap; }
.pill.buy { background:var(--good-bg); color:var(--good); }
.pill.sell { background:var(--bad-bg); color:var(--bad); }
.pill.warn { background:var(--warn-bg); color:var(--warn); }
.pill.hold { background:var(--hold-bg); color:var(--muted); }
.card { background:var(--surface); border:1px solid var(--line); border-left-width:4px;
  border-radius:6px; padding:1.1rem 1.25rem; margin-bottom:1.25rem; }
.card.buy { border-left-color:var(--good); }
.card.sell { border-left-color:var(--bad); }
.card.hold { border-left-color:var(--muted); }
.card.warn { border-left-color:var(--warn); }
.card-head { display:flex; justify-content:space-between; gap:1rem; flex-wrap:wrap; }
.card h3 { margin:0; font-family:Georgia,serif; font-size:1.15rem; }
.ticker { color:var(--muted); font-weight:400; font-size:.85rem; }
.price-line { font-size:1.05rem; margin-top:.2rem; }
.score-block { text-align:right; min-width:11rem; }
.meter { height:6px; background:var(--line); border-radius:3px; margin:.5rem 0 .3rem; }
.meter-fill { height:100%; border-radius:3px; background:var(--muted); }
.meter-fill.buy { background:var(--good); }
.meter-fill.sell { background:var(--bad); }
.meter-fill.warn { background:var(--warn); }
.score-num { font-size:.85rem; }
.conclusion { font-size:1.02rem; font-weight:500; margin:.9rem 0; }
.two-col { display:grid; grid-template-columns:1fr 1fr; gap:0 2rem; }
@media (max-width:640px) { .two-col { grid-template-columns:1fr; } }
.card h4 { font-size:.72rem; text-transform:uppercase; letter-spacing:.08em;
  color:var(--muted); margin:1rem 0 .4rem; }
.kv { list-style:none; margin:0; padding:0; font-size:.9rem; }
.kv li { display:flex; gap:.75rem; padding:.25rem 0; border-bottom:1px dotted var(--line); }
.kv li > span:first-child { flex:0 0 6.5rem; color:var(--muted); font-size:.82rem; }
.plan { display:grid; grid-template-columns:1fr 1fr; gap:.5rem; }
.plan-item { background:var(--bg); border:1px solid var(--line); border-radius:4px; padding:.45rem .6rem; }
.plan-label { font-size:.7rem; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); }
.plan-val { font-size:.88rem; }
.checklist { list-style:none; margin:0; padding:0; font-size:.88rem; }
.checklist li { padding:.18rem 0; }
.risk { margin:.9rem 0 0; font-size:.88rem; color:var(--warn);
  background:var(--warn-bg); padding:.5rem .8rem; border-radius:4px; }
.empty { background:var(--surface); border:1px dashed var(--line); border-radius:6px;
  padding:2rem; text-align:center; color:var(--muted); }
.disclaimer { margin-top:2.5rem; padding-top:1rem; border-top:3px double var(--line);
  font-size:.82rem; color:var(--muted); }
"""

_SCRIPT = """
async function poll() {
  try {
    const r = await fetch('/api/status');
    const s = await r.json();
    const log = document.getElementById('runlog');
    const btn = document.getElementById('runbtn');
    if (log) log.textContent = s.log.join('\\n');
    if (log) log.scrollTop = log.scrollHeight;
    if (s.status === 'running') {
      if (btn) { btn.disabled = true; btn.textContent = 'Running…'; }
      setTimeout(poll, 2000);
    } else {
      if (btn) { btn.disabled = false; btn.textContent = 'Run analysis'; }
      if (window._wasRunning) location.reload();
    }
    window._wasRunning = (s.status === 'running');
  } catch (e) { setTimeout(poll, 4000); }
}
async function startRun(ev) {
  ev.preventDefault();
  const stocks = document.getElementById('stocks').value.trim();
  const noLlm = document.getElementById('nollm').checked;
  await fetch('/api/run', { method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ stocks: stocks, no_llm: noLlm }) });
  window._wasRunning = true;
  poll();
}
window.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('runform');
  if (form) form.addEventListener('submit', startRun);
  poll();
});
"""


def _fmt(value: Optional[float], digits: int = 2, prefix: str = "") -> str:
    if value is None:
        return "n/a"
    try:
        return f"{prefix}{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"


def _delta(value: Optional[float], digits: int = 2, suffix: str = "%") -> str:
    if value is None:
        return '<span class="muted">n/a</span>'
    cls = "up" if value >= 0 else "down"
    return f'<span class="num {cls}">{value:+.{digits}f}{suffix}</span>'


def _signal_class(signal: str) -> str:
    if "BUY" in signal:
        return "buy"
    if "SELL" in signal:
        return "sell"
    if "RISK" in signal:
        return "warn"
    return "hold"


def _market_section(market: Optional[MarketContext]) -> str:
    if market is None:
        return '<div class="empty">Market context not loaded yet — run an analysis or refresh shortly.</div>'
    cards = []
    for idx in market.indices:
        if idx.level is None:
            continue
        cards.append(
            f'<div class="idx"><div class="idx-name">{_e(idx.name)}</div>'
            f'<div class="idx-level num">{idx.level:,.2f}</div>'
            f'<div class="idx-deltas">{_delta(idx.change_pct)}'
            f'<span class="muted num">5d {_fmt(idx.return_5d_pct, 1)}%</span>'
            f'<span class="muted num">20d {_fmt(idx.return_20d_pct, 1)}%</span></div></div>'
        )
    out = f'<div class="idx-grid">{"".join(cards)}</div>'
    fii, dii = market.fii_net(), market.dii_net()
    if fii is not None or dii is not None:
        out += (
            f'<p class="flows">Provisional cash flows — FII net {_delta(fii, 0, " cr")} · '
            f'DII net {_delta(dii, 0, " cr")} (₹, NSE)</p>'
        )
    return out


def _summary_table(results: List[Dict[str, Any]]) -> str:
    rows = []
    for r in results:
        sig = r.get("signal_type", "")
        rows.append(
            f'<tr><td><a href="#{_e(r["symbol"])}" class="sym">{_e(r["symbol"])}</a></td>'
            f'<td class="num">{_fmt(r.get("price"), 2, "₹")}</td>'
            f'<td>{_delta(r.get("change_pct"))}</td>'
            f'<td class="num">{r.get("sentiment_score", 0)}</td>'
            f'<td><span class="pill {_signal_class(sig)}">{_e(sig)}</span></td>'
            f'<td><strong>{_e(r.get("operation_advice", ""))}</strong></td></tr>'
        )
    return (
        '<div class="table-scroll"><table><thead><tr><th>Stock</th><th>Price</th>'
        "<th>Day</th><th>Score</th><th>Signal</th><th>Advice</th></tr></thead>"
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def _stock_card(r: Dict[str, Any]) -> str:
    d = r.get("dashboard") or {}
    core = d.get("core_conclusion") or {}
    tech = d.get("technical_read") or {}
    plan = d.get("trade_plan") or {}
    levels = tech.get("key_levels") or {}
    pos = core.get("position_advice") or {}
    sig = r.get("signal_type", "")
    cls = _signal_class(sig)
    score = r.get("sentiment_score", 0)

    checklist = "".join(f"<li>{_e(str(i))}</li>" for i in (plan.get("action_checklist") or []))
    plan_rows = "".join(
        f'<div class="plan-item"><div class="plan-label">{label}</div>'
        f'<div class="plan-val">{_e(str(plan.get(key)))}</div></div>'
        for label, key in (
            ("Entry zone", "entry_zone"),
            ("Stop loss", "stop_loss"),
            ("Target 1", "target_1"),
            ("Target 2", "target_2"),
        )
        if plan.get(key)
    )
    risk = d.get("risk_warning") or ""
    conclusion = core.get("one_sentence") or r.get("analysis_summary") or ""

    return f"""
    <article class="card {cls}" id="{_e(r["symbol"])}">
      <header class="card-head">
        <div>
          <h3>{_e(r.get("name", r["symbol"]))} <span class="ticker num">{_e(r["symbol"])}</span></h3>
          <div class="price-line num">{_fmt(r.get("price"), 2, "₹")} {_delta(r.get("change_pct"))}</div>
        </div>
        <div class="score-block">
          <span class="pill {cls}">{_e(sig)}</span>
          <div class="meter" role="img" aria-label="score {score} of 100">
            <div class="meter-fill {cls}" style="width:{score}%"></div>
          </div>
          <div class="score-num num">{score}<span class="muted">/100</span> · {_e(r.get("operation_advice", ""))}</div>
        </div>
      </header>
      <p class="conclusion">{_e(str(conclusion))}</p>
      <div class="two-col">
        <div>
          <h4>Technical read</h4>
          <ul class="kv">
            <li><span>Trend</span>{_e(str(tech.get("trend_status") or "n/a"))}</li>
            <li><span>Momentum</span>{_e(str(tech.get("momentum") or "n/a"))}</li>
            <li><span>Volume</span>{_e(str(tech.get("volume_signal") or "n/a"))}</li>
            <li><span>Support</span><span class="num">{_fmt(levels.get("support"), 2, "₹")}</span></li>
            <li><span>Resistance</span><span class="num">{_fmt(levels.get("resistance"), 2, "₹")}</span></li>
          </ul>
          <h4>Positioning</h4>
          <ul class="kv">
            <li><span>No position</span>{_e(str(pos.get("no_position") or "n/a"))}</li>
            <li><span>Holding</span>{_e(str(pos.get("has_position") or "n/a"))}</li>
          </ul>
        </div>
        <div>
          <h4>Trade plan</h4>
          <div class="plan">{plan_rows}</div>
          <h4>Checklist</h4>
          <ul class="checklist">{checklist}</ul>
        </div>
      </div>
      {f'<p class="risk">⚠ {_e(str(risk))}</p>' if risk else ""}
    </article>"""


def render_dashboard(
    results: List[Dict[str, Any]],
    market: Optional[MarketContext],
    with_controls: bool = False,
    stock_list: str = "",
) -> str:
    """Full self-contained dashboard page."""
    today = datetime.now().strftime("%A, %d %B %Y")
    engine = results[0].get("analysis_source", "—") if results else "—"
    as_of = market.as_of if market and market.as_of else "latest close"
    regime = _e(market.regime_hint) if market else "market context not loaded"

    controls = ""
    if with_controls:
        controls = f"""
  <form class="controls" id="runform">
    <input type="text" id="stocks" placeholder="Symbols, e.g. RELIANCE,TCS,HDFCBANK (blank = configured watchlist)"
           value="{_e(stock_list)}">
    <label><input type="checkbox" id="nollm"> rule-based only</label>
    <button type="submit" id="runbtn">Run analysis</button>
  </form>
  <pre class="runlog" id="runlog"></pre>"""

    body = (
        '<div class="empty">No analyses yet — run one above to populate the dashboard.</div>'
        if not results
        else _summary_table(results)
        + "<h2>Research notes</h2>"
        + "".join(_stock_card(r) for r in results)
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>India Stock Research — Dashboard</title>
<style>{_CSS}</style>
</head>
<body>
<div class="wrap">
  <header class="masthead">
    <div class="date">{_e(today)} · NSE / BSE · Data as of {_e(as_of)}</div>
    <h1>India Stock Research</h1>
    <p class="regime"><strong>Regime read:</strong> {regime}</p>
    <p class="engine">Analysis engine: {_e(engine)}</p>
  </header>
  {controls}
  <h2>Market context</h2>
  {_market_section(market)}
  <h2>Watchlist</h2>
  {body}
  <footer class="disclaimer">
    <strong>Disclaimer:</strong> generated automatically for research and education only.
    Not investment advice; the author is not a SEBI-registered investment adviser.
    Markets involve risk — do your own diligence before acting.
  </footer>
</div>
{f"<script>{_SCRIPT}</script>" if with_controls else ""}
</body>
</html>"""
