# CBSE Finances

Minimal, local, file-based financial planner for two people. Runs on one Mac via Streamlit. No server, no database, no auth, no live market data.

It is a **contributions-vs-goal** tracker (a port of the household's spreadsheet model), *not* a market-value/net-worth tracker: it answers "did we invest what the plan says we should this year?" — not "what is the portfolio worth today?"

## Run

```sh
uv sync
uv run streamlit run app.py     # opens http://localhost:8501
uv run pytest                   # tests
```

## The model

Everything derives from **income**:

1. **Budget split** — each person's income splits into needs / wants / investment. The anchor year (earliest) splits **50/30/20**; every year after, only the income *increment* splits **20/30/50** (invest more as you earn more). Fully derived — you only enter income.
2. **Target allocation** — each person has a two-tier target (constant by default, editable per year): `long_term` for investment money, `short_term` for the invested slice of wants money (`wants_invest_pct`).
3. **Planned (expected) contributions** — `investment × long_term%  +  (wants × wants_invest_pct) × short_term%`, per category. Reproduces the source sheet to the rupee.
4. **Plan vs actual** — planned vs what was actually invested (`contributions.csv`): shortfall, % goal achieved, drawdown chart, emergency-fund goal.

## Data

The data folder is the database. It lives **outside the repo** (iCloud Drive, auto-backed-up) and is referenced by `DATA_DIR` in `.env` (copy `.env.example`). The app re-reads files on every refresh and never caches. Everything is editable in-app (Update Data page) or directly in any editor / Numbers.

```
FinanceData/
  config.yaml        # usd_inr_rate, categories (asset classes)
  profiles/
    rv.yaml          # birth_year, forward_increment_pct, wants_invest_pct, default_target
    partner.yaml     # (filename stem = the `profile` key used in every CSV)
  income.csv         # profile,year,salary,bonus,other          ← drives everything
  targets.csv        # profile,year,tier,category,pct            ← per-year overrides (optional)
  contributions.csv  # year,profile,category,amount,notes        ← actuals invested
  goals.csv          # year,profile,emergency_fund_goal
```

The budget (needs/wants/investment) is **derived from income**, not stored. Categories are asset classes: `us_market, indian_stocks, mfs, fixed_deposit, ppf_nps, bonds_gsec_aif, gold_metals`. Pydantic validates the YAML; `storage.py` validates each CSV against the config on load and fails fast on bad hand-edits.

## Pages

The nav reads as the money pipeline; **each page edits its own data in place** (no separate edit page):

- **Dashboard** *(landing)* — where do we stand this year: % goal, invested vs planned, cumulative curve
- **Income** — what came in: editable grid per person/year
- **Budget** — how it splits: all years at once (2023 → current+3 projected at 5%), derived, read-only
- **Target** — where investment should go: editable % per year with auto-calculated ₹ (carry-forward)
- **Monthly Plan** — what to do this month: ₹/month per instrument
- **Plan vs Actual** — did we do it: planned vs actual, shortfall, % goal; actuals edited here

Visuals: grayscale + two accents — **teal** (what happened) and **mulberry** (what's planned/projected). The top-right **View** multiselect filters every page (combined when 2+).

## Decisions

- **Contributions-vs-goal, not net worth** (2026-06-12) — the app deliberately tracks invested-vs-planned cash flow, mirroring the household spreadsheet. The earlier holdings/market-value design in the Obsidian spec was superseded before build.
- Single Mac, both users share the laptop; data in iCloud Drive.
- Separate per person, with a combined view.
- App name: **CBSE Finances**.

## Roadmap (not built yet)

1. Zerodha Console export → auto-fill `contributions.csv`
2. Auto-project income/budget forward to a horizon (currently reflects entered years only)
3. Backfill the full 2023+ history from the old workbook

## Non-goals

Live prices/FX, broker APIs, market-value/net-worth tracking, auth, multi-device sync, mobile, expense tracking, cloud hosting.
