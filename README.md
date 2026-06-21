# CBSE Finances — Architecture

A local Streamlit app (repo folder `hisaab-tracker`) that replaces a misbehaving
Excel workbook. It runs on a single Mac for two people: Rv (display name
"Brownie") and his wife ("Cheeni", currently an empty placeholder profile).

It is a **contributions-vs-goal tracker**: did we invest what the plan says for
each year? It is *not* a net-worth or market-value tracker — it never looks at
what holdings are worth today, only at what was planned and what was actually
contributed.

## The model

Income drives everything.

- **Income** is entered monthly and aggregated to a yearly total per person
  (`salary + bonus + other`).
- **Budget** (needs / wants / investment) is *derived* from income, never
  stored. A person's **anchor year** (their earliest) splits total income
  **50/30/20**. Every later year carries the previous rupee amounts forward and
  splits only the income **increment 20/30/50**, so raises flow mostly to
  investing. Beyond the entered years it projects forward to *current year + 3*,
  growing income by each profile's `forward_increment_pct` (default 5%) and
  splitting each projected raise 20/30/50. `budget_series` also surfaces YoY
  income growth % and the `job_change` flag per year.
- **Targets** say where the year's *investment amount* goes, as a single
  `{category: percent}` map summing to 100. The whole goal is that investment
  split by the target — nothing is carried from wants:

  ```
  expected[category] = investment × target%[category]
  ```

  Per-year overrides carry forward — the most recent override year ≤ the asked
  year wins; otherwise the profile's `default_target` applies.
- **Actual** comes from `contributions.csv`; the gap is the shortfall.
  `%goal achieved = total actual ÷ total expected`.

## Data files & schema

The data folder **is** the database. It lives **outside the repo** in iCloud
Drive (`~/Library/Mobile Documents/com~apple~CloudDocs/FinanceData`), is pointed
to by `DATA_DIR` in `.env` at the repo root, is gitignored, and is never
committed. Every page re-reads it on each render — nothing is cached.

| File | Keyed by | Columns / shape |
|------|----------|-----------------|
| `income.csv` | profile, year, month | `profile, year, month (1–12), salary, bonus, other, job_change`. Monthly rows. RSU is **not** a column — it folds into `other` (which also covers FD/RD maturity, etc.). `job_change` is a per-year 0/1 flag repeated across the year's 12 rows. |
| `contributions.csv` | year, profile | `year, profile, category, amount, notes` — what was actually invested. |
| `targets.csv` | profile, year, category | `profile, year, category, pct`. Optional per-year overrides; each `(profile, year)` must sum to 100. |
| `goals.csv` | year, profile | `year, profile, emergency_fund_goal`. |
| `config.yaml` | — | `usd_inr_rate, usd_inr_as_of, categories` (the asset classes: `us_market, indian_stocks, mfs, fixed_deposit, ppf_nps, bonds_gsec_aif, gold_metals`). |
| `profiles/<key>.yaml` | — | `name, birth_year, forward_increment_pct, default_target` (a `{category: percent}` map summing to 100). The filename stem is the profile **key** used in the `profile` column of every CSV. |

Budget is not a file — it is derived from income at read time. `storage.py`
validates each CSV against the config and profiles on load and fails fast on bad
hand-edits; pydantic (`models.py`) validates the YAML.

## Code structure

- **`finance_tracker/config.py`** — central config: the palette, budget-model
  constants (`BASE_SPLIT`, `INCREMENT_SPLIT`, `PROJECTION_YEARS_AHEAD`,
  `ON_TRACK_PCT`), `INCOME_COMPONENTS`, and `CATEGORY_LABELS`.
- **`finance_tracker/models.py`** — pydantic schemas (`Config`, `Profile`,
  `Target`) validating the hand-edited YAML.
- **`finance_tracker/storage.py`** — load/save and validation for the data
  folder, the column constants, and `.env` `DATA_DIR` resolution.
- **`finance_tracker/compute.py`** — the financial model as pure functions:
  `annual_income`, `budget_series`, `expected_contributions`, `plan_vs_actual`,
  `household_plan_vs_actual`, `pct_goal_achieved`, `resolve_target`,
  `available_years`, and friends.
- **`finance_tracker/ui.py`** — Streamlit presentation: the `Data` snapshot and
  `load_all`; formatting (`inr`, `inr_short`, `pretty_category`); styling
  (`inject_theme`, `metric_tile`, `html_table`, `style_fig`, `page_header`).
- **`views/*.py`** — the six pages.
- **`app.py`** — `st.set_page_config`, logo, theme injection, and
  `st.navigation`.
- **`tests/`** — `test_compute.py` (golden ₹-exact figures and `%goal`) and
  `test_app_smoke.py` (renders every page headlessly). 20 tests, all passing.

## Pages

Navigation reads as the money pipeline — in → split → destination → monthly
action → verdict. **Dashboard** is the default landing page. Each page has a
top-right **View** multiselect that scopes every figure to the selected people
(combined when 2+). **Each page edits its own data in place** — there is no
separate Update-Data page.

- **Dashboard** *(landing)* — year snapshot (goal progress, income, savings
  rate), all-time invested-to-date strip, income-vs-investment trajectory chart,
  plan-vs-actual by bucket, and year-specific takeaways.
- **Income** — income-over-time chart and a 12-month editable grid per person
  (salary/bonus/other, job-change flag, "copy January down").
- **Budget** — the derived split for a chosen year, the investment slice year by
  year (100%-stacked), and a full detail table (all years + projections, current
  year highlighted, projected years muted).
- **Target** — the allocation in force this year with auto-calculated rupee
  amounts, plus an editor for per-year target overrides.
- **Monthly Plan** — what to invest each month per instrument
  (`target % × this year's budget ÷ 12`).
- **Plan vs Actual** — planned vs actual per category for a year, `%goal`,
  emergency-fund goal, and in-place editors for contributions and goals.

## Visual language

Light theme. **Inter** font. A grayscale base plus two accents:
**teal `#0F766E`** for actuals / the current year, **mulberry `#86198F`** for
planned / projected / target figures. Charts are Plotly themed via `style_fig`;
KPIs are bordered tiles (`metric_tile`); read-only tables are themed HTML
(`html_table`); cards use compact ₹ lakh/crore formatting (`inr_short`).

A custom dark mode was attempted and removed: Streamlit can't reliably drive one
— injected CSS is torn down on navigation and can't repaint native data grids.
(Streamlit's own light/dark toggle still lives under ☰ → Settings, but the app
is designed for light only.)

## How to run

```sh
uv sync
uv run streamlit run app.py
```

Tests:

```sh
uv run pytest
```

Requires Python ≥ 3.14. Before first run, copy `.env.example` to `.env` and set
`DATA_DIR` to the data folder.

## Non-goals

Live prices or FX, broker APIs, market-value / net-worth tracking, auth,
multi-device sync, mobile, cloud hosting, and a custom dark mode. Local only —
no server, no database, no live market data.
