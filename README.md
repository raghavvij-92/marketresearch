<div align="center">

# 🇮🇳 India Stock Researcher

**AI-powered, end-to-end daily research pipeline for NSE / BSE equities**

Technicals · Fundamentals · News · FII/DII flows · LLM decision dashboards · Multi-channel push

Architecture adapted for the Indian market from
[ZhuLinsen/daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis).

</div>

---

## What it does

Every run (locally, in Docker, or on a free GitHub Actions schedule after market close) the pipeline:

1. **Parses your watchlist** — NSE symbols (`RELIANCE`, `M&M`, `BAJAJ-AUTO`), BSE scrip codes (`500325`) or suffixes (`TCS.BO`), and indices (`NIFTY`, `BANKNIFTY`, `SENSEX`).
2. **Builds market context** — NIFTY 50, SENSEX, NIFTY Bank, NIFTY IT, NIFTY Midcap 50, **India VIX**, USD/INR, Brent crude, plus **provisional FII/DII cash flows** from NSE — so stock calls are framed by the day's regime.
3. **Fetches per-stock data** — ~2 years of daily OHLCV and a fundamentals snapshot (PE, PB, ROE, growth, margins, SEBI-style market-cap bucket) from Yahoo Finance, enriched with NSE-only signals: **delivery percentage**, price band / circuit limits, F&O membership, and corporate announcements.
4. **Computes a full technical snapshot** — SMA 5/10/20/50/200 stack & bias, RSI(14), MACD(12,26,9) with crossover detection, Stochastic, Bollinger bands, ATR, volume ratio & OBV accumulation, 52-week structure, swing support/resistance, pivot points, and a 0–100 composite trend score.
5. **Gathers news** — free Google News RSS per stock + market headlines from Economic Times, Moneycontrol, LiveMint and Business Standard (optional Tavily / SerpAPI for stronger retrieval).
6. **Runs the AI analyst** — an LLM (Gemini / any OpenAI-compatible API / Anthropic) produces a structured **decision dashboard**: core conclusion, guidance for holders vs non-holders, technical & fundamental reads, risk alerts and catalysts, a ₹-denominated **trade plan** (entry zone, stop loss, targets, sizing), an action checklist, and signal attribution. With no API key configured, a deterministic **rule-based engine** produces the same dashboard from technicals alone — the pipeline never comes back empty.
7. **Delivers** — full markdown research notes per stock + a daily digest, history persisted to SQLite, and a compact summary pushed to **Telegram / Discord / Slack / Email**.

### Sample output

```
🟢 RELIANCE  ₹1,323.90 -0.26% · 81/100 · BUY
   RELIANCE shows a bullish technical setup (trend score 81/100).
🟡 TCS       ₹3,412.55 +0.12% · 66/100 · ACCUMULATE
🔴 HDFCBANK  ₹951.60  -0.85% · 23/100 · SELL
```

Each stock also gets a full research note (`reports/YYYY-MM-DD/SYMBOL.md`) with the complete dashboard, and `reports/YYYY-MM-DD/digest.md` combines market context + headlines + all notes.

---

## Quick start

### Option 1 — GitHub Actions (recommended, zero servers)

1. **Fork / use this repository.**
2. Add repository secrets under `Settings → Secrets and variables → Actions`:

   | Secret | Required | Notes |
   |---|---|---|
   | `STOCK_LIST` | ✅ | e.g. `RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK` |
   | `GEMINI_API_KEY` | one LLM key recommended | free tier at [aistudio.google.com](https://aistudio.google.com) |
   | `OPENAI_API_KEY` (+ `OPENAI_BASE_URL`, `OPENAI_MODEL`) | alt. | works with DeepSeek, Groq, etc. |
   | `ANTHROPIC_API_KEY` | alt. | Claude models |
   | `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | optional | via [@BotFather](https://t.me/BotFather) |
   | `DISCORD_WEBHOOK_URL` / `SLACK_WEBHOOK_URL` | optional | |
   | `EMAIL_SENDER` + `EMAIL_PASSWORD` + `EMAIL_RECEIVERS` | optional | Gmail needs an App Password |
   | `TAVILY_API_KEY` / `SERPAPI_API_KEY` | optional | better news retrieval |

3. Done. The workflow runs **Mon–Fri at 18:00 IST** (after NSE close, once delivery data and provisional FII/DII flows publish), uploads reports as build artifacts, and pushes notifications. You can also trigger it manually from the Actions tab (with a custom stock list).

> No LLM key? The pipeline still runs in rule-based mode — pass `no_llm: true` on manual dispatch or simply configure no key.

### Option 2 — Local

```bash
git clone <this-repo> && cd marketresearch
pip install -r requirements.txt
cp .env.example .env        # edit: STOCK_LIST, one LLM key, optional notifiers

python main.py                          # analyze your watchlist
python main.py --stocks RELIANCE,TCS    # ad-hoc list
python main.py --no-llm                 # rule-based only (no key needed)
python main.py --market-only            # just the market context + headlines
python main.py --no-notify              # don't push, just write reports
```

Reports land in `reports/<date>/`, the latest digest is mirrored to `reports/latest.md`, and every result is stored in `data/analysis_history.db` (SQLite) for later review/backtesting.

### Web dashboard

```bash
python webui.py            # → http://127.0.0.1:8000
```

A zero-dependency (stdlib-only) local dashboard: live market context (indices, India VIX, FII/DII flows), the latest research note per stock with signal pills, score meters and trade plans, plus a **Run analysis** button that executes the full pipeline in the background and streams its log to the page. Use `--port` / `--host` to change the bind address.

---

## Architecture

```
main.py ──► symbols ──► DataManager ─────► indicators ──► StockAnalyzer ──► report ──► notification
                │            │                                  │             │            │
                │            ├─ yahoo_fetcher (OHLCV,          LLM client     │        Telegram
                │            │   fundamentals; direct API      (Gemini /      │        Discord
                │            │   + yfinance fallback)          OpenAI-compat/ │        Slack
                │            └─ nse_fetcher (delivery %,       Anthropic)     │        Email
                │                circuits, announcements,       │             │
                │                FII/DII)                      rule-based     └──► storage (SQLite)
                └─ market_context (NIFTY/SENSEX/BankNifty/     fallback
                   VIX/USDINR/Brent + FII-DII regime read)
```

Design principles carried over from the reference project:

* **Graceful degradation everywhere** — every external source (NSE, news feeds, fundamentals, the LLM itself) is best-effort; a failure narrows the report, never kills the run.
* **Structured LLM output** — the model must return a strict JSON dashboard; responses are fence-stripped, brace-matched and repaired, and unparseable output falls back to the rule engine with the error surfaced in the report.
* **India-aware analysis discipline** — the prompt encodes local market mechanics: delivery-percentage interpretation, circuit bands, FII/DII regime, India VIX levels, SEBI market-cap buckets, and a hard rule against chasing over-extended moves.

## Project layout

```
main.py                     CLI orchestrator
webui.py                    local web dashboard (stdlib http.server)
src/config.py               env-driven configuration
src/symbols.py              NSE/BSE/index symbol normalisation
src/data_provider/
  yahoo_fetcher.py          OHLCV + fundamentals (direct API, yfinance fallback)
  nse_fetcher.py            delivery %, circuits, announcements, FII/DII
  manager.py                provider orchestration
src/indicators.py           full technical engine (pure pandas/numpy)
src/market_context.py       index / VIX / flows regime snapshot
src/news.py                 Google News RSS + Indian financial press (+ Tavily/SerpAPI)
src/llm.py                  Gemini / OpenAI-compatible / Anthropic REST client
src/analyzer.py             decision-dashboard prompt, JSON parsing, rule engine
src/report.py               markdown research notes, digest, notification text
src/storage.py              SQLite history
src/notification/           Telegram / Discord / Slack / Email senders
tests/                      offline test suite (no network needed)
```

## Testing

```bash
pip install pytest
pytest tests/ -v
```

The suite (32 tests) runs fully offline against synthetic OHLCV data and covers symbol parsing, every indicator, the rule engine (including the over-extension guard), LLM JSON extraction edge cases, report rendering, message chunking and storage.

---

## ⚠️ Disclaimer

This project is for **research and education only**. It is **not investment advice**, and the authors are **not SEBI-registered investment advisers**. Equity markets involve risk of loss; AI-generated analysis can be wrong. Always do your own diligence or consult a registered adviser before trading.

## Credits

* Pipeline architecture inspired by [ZhuLinsen/daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis) (MIT).
* Market data via Yahoo Finance and NSE India public endpoints; news via Google News and the Indian financial press RSS feeds. Respect their terms of use — this tool is for personal research at human scale.
