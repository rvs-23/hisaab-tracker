# Personal Finances Tracker

A local Streamlit app for two people that replaces a finance-tracking Excel. It
answers one question — *did we invest what the plan said this year?* — so it's a
**contributions-vs-goal** tracker, not a net-worth one. Income drives a derived
budget, a target allocation, and a planned-vs-actual comparison.

## Getting started

```sh
uv sync
cp .env.example .env          # then set DATA_DIR to your data folder
uv run streamlit run app.py   # opens http://localhost:8501
```

Requires Python ≥ 3.14. Tests: `uv run pytest`.

## Using the app & feeding in data

Your data lives in a **plain CSV/YAML folder outside the repo** (e.g. in iCloud
or Drive), pointed to by `DATA_DIR` in `.env`. It's never committed. You enter
everything **through the app**, working down the sidebar in order — each page
edits its own files in place, and the app re-reads from disk on every refresh.

The sidebar has a **Profile switch**: the app shows **one person at a time**
(routing), so each of you fills your own data with no overlap. (A combined
household view is planned, but kept separate.)

1. **Income** — pick a year and fill the 12 months (`salary`, `bonus`, `other` —
   put RSU vesting or an FD/RD maturing under *other*); tick *job change* if you
   switched jobs that year. Everything else is derived from this.
2. **Budget** — read-only. Shows how income splits into needs/wants/investment
   and how the investment slice grows. Nothing to fill here; change it on Income.
3. **Allocation** — set the **%** per instrument (must sum to 100); the ₹/year
   and ₹/month fill in automatically from that year's investment amount.
4. **Actuals** — record what you **actually** invested per instrument, and your
   emergency-fund goal. The page shows planned vs actual and your % of goal.
5. **Dashboard** — the consolidated **journey** (not one year): the earning/
   investing trajectory, lifetime cards (potential net worth, invested to date,
   overall goal achieved, savings rate), a net-worth chart (invested vs projected
   value, with a 5-year projection), and planned-vs-actual per year. Read-only.

Prefer a text editor? Every file is plain CSV/YAML, so you can edit them
directly and refresh the app. The files:

| File | Columns / shape |
|------|-----------------|
| `income.csv` | `profile, year, month (1–12), salary, bonus, other, job_change`. Monthly rows; `job_change` is a per-year 0/1 flag. |
| `targets.csv` | `profile, year, category, pct`. Per-year allocation overrides; each `(profile, year)` sums to 100. Optional — the profile's `default_target` is the fallback. |
| `contributions.csv` | `year, profile, category, amount, notes` — what was actually invested. |
| `goals.csv` | `year, profile, emergency_fund_goal`. |
| `config.yaml` | `usd_inr_rate, usd_inr_as_of, categories` (the asset classes). |
| `profiles/<key>.yaml` | `name, birth_year, forward_increment_pct, default_target` (a `{category: percent}` map summing to 100). The filename stem is the `profile` key used across the CSVs. |

A `.env` pointing at a folder with `config.yaml` and a `profiles/` directory is
the minimum to start; the CSVs are created as you save from the app.

## How the numbers work

- **Budget** is *derived* from income, never stored. A person's **anchor year**
  (earliest) splits income **50/30/20** across needs/wants/investment; every
  later year carries the previous rupees forward and splits only the income
  **increment 20/30/50**, so raises flow mostly to investing. Beyond the entered
  years it projects to *current year + 3* at `forward_increment_pct` (default 5%).
- **The goal** for a year is that year's investment amount split by the target:
  `expected[category] = investment × target%[category]`. Per-year target
  overrides carry forward until a newer one replaces them.
- **Potential net worth** is a projection (no live market value): each
  contribution compounded at a conservative per-category return (`EXPECTED_RETURNS`
  in `config.py`), plus the emergency fund. The dashboard shows actual invested
  vs this potential, and projects it ~5 years out.
- **% goal achieved** = total actual ÷ total expected. `storage.py` validates
  every file on load and refuses bad hand-edits.

## Code structure

Flat — modules at the root, page scripts in `views/`:

- **`config.py`** — palette, budget-model constants (`BASE_SPLIT`,
  `INCREMENT_SPLIT`, `PROJECTION_YEARS_AHEAD`, `ON_TRACK_PCT`),
  `INCOME_COMPONENTS`, `CATEGORY_LABELS`.
- **`models.py`** — pydantic schemas (`Config`, `Profile`) for the YAML.
- **`storage.py`** — load/save + validation for the data folder; `.env`
  `DATA_DIR` resolution.
- **`compute.py`** — the financial model as pure functions (`budget_series`,
  `expected_contributions`, `plan_vs_actual`, `resolve_target`, …).
- **`ui.py`** — Streamlit presentation: `load_all`, formatting, and the shared
  styling helpers (`metric_tile`, `html_table`, `style_fig`, `edit_card`, …).
- **`views/*.py`** — the five pages. **`app.py`** — config, logo, `st.navigation`.
- **`tests/`** — `test_compute.py` (golden figures) and `test_app_smoke.py`
  (renders every page headlessly).

## Non-goals

Live prices/FX, broker APIs, market-value/net-worth tracking, auth, multi-device
sync, mobile, cloud hosting. Local only — no server, no database, no live data.
