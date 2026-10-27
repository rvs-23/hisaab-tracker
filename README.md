# Personal Finances Tracker

A local Streamlit app for two people that replaced a finance-tracking Excel.
It answers one question: **did we invest what the plan said this year?** So it
tracks **contributions vs goal**. You enter income; the budget, the goal, and
the plan-vs-actual comparison are derived from it. Balances are never entered.
Where a portfolio value appears, it is an *estimate* from contributions and an
expected return, and is labelled that way.

New here? **[docs/how-it-works.md](docs/how-it-works.md)** is the 5-minute,
no-jargon guide.

## Run it

```sh
uv sync
cp .env.example .env          # set DATA_DIR to your data folder
uv run streamlit run app.py   # http://localhost:8501/?profile=rv
uv run pytest                 # tests
```

Python ≥ 3.14. `app.py` is the entry point; pages are wired with `st.navigation`.

## Data

Plain CSV/YAML in a folder **outside the repo** (`DATA_DIR` in `.env`, never
committed), re-read from disk on every render. No database, no caching.

| File | What it holds | Written by |
|---|---|---|
| `config.yaml` | `categories`, optional `expected_return_pct` | hand |
| `profiles/<key>.yaml` | `name, birth_year, forward_increment_pct, default_target` | hand |
| `income.csv` | monthly `salary / bonus / other`, `job_change` flag | Income page |
| `contributions.csv` | what was invested, per year and category, with `notes` (shown as Details) and `last_change` | Investments page, importer |
| `targets.csv` | per-year target-allocation overrides | Budget page |
| `adjustments.csv` | `opening_corpus`, `emergency_fund` per person | Dashboard, Investments |
| `changes.jsonl` | append-only audit log of every save | every save |

The minimum to start is `config.yaml` + one profile; scaffold both with
`uv run python scripts/init_data_dir.py <path>`. The CSVs appear on first save.

**Every save** validates first and refuses bad input with a message. Checks:
numeric, non-negative (except income's *other*, which may go negative for a
tax payment or clawback), known categories and profiles, no duplicates, and %s
that sum to 100. Each CSV is replaced atomically (temp file + `os.replace`).
Each accepted save then appends the rows added and removed to `changes.jsonl`.
If only that audit write fails, the page says *saved, but not audited*. Editors
also check whether the data on disk changed since you opened them (say, from
another tab). If it did, they reload instead of overwriting.

**Zerodha import:** `uv run python scripts/import_tradebook.py <tradebook.csv>
--profile <key> --year <year>` collapses one year of fills into a single net
(buys − sells) contribution row. It uses the same validation and audit path.
Add `--dry-run` to preview or `--replace` to overwrite an existing row.

**Zerodha summary:** `uv run python scripts/zerodha_summary.py <tradebook.csv>...`
is read-only. It takes any mix of equity and MF exports (overlaps are
de-duplicated) and prints buys, sells and net per year, `--by month` or
`--by symbol`, optionally within `--year` or `--from`/`--to`.

## People

One person at a time, chosen by URL: `?profile=rv` or `?profile=cheeni`. It
sticks across pages. There's no switcher and no name on screen; each person
has their own accent colours. Year pickers run from 2022 to the current year.

`?profile=household` (teal) is both people combined. It isn't a profile file;
it sums the real people. It only reads, so its nav is just Dashboard and
House fund: income, budget and actuals are edited per person.

Every page shows, under its title, when that person (or, for the household,
anyone) last saved data, from `changes.jsonl`.

## Pages

| Page | Question it answers | Writes |
|---|---|---|
| **Dashboard** | Where am I overall? Tiles, the year-on-year journey chart, allocation to date, catch-up, health nudges | opening corpus (Adjustments expander) |
| **Income** | What did I earn? 12-month grid per year; a new year pre-fills last year's salary | `income.csv` |
| **Budget** | How does income split, and where should the investment go? | `targets.csv` (allocation editor) |
| **Investments** | Record what went in; how does it compare with the plan? | `contributions.csv`, emergency fund held |
| **House fund** (household) | If we keep investing at this pace, how much could we put down on a house at the end of each year? | nothing (live inputs) |

## The model

- **Budget** is derived, never stored. The first *earning* year splits income
  by the base split (needs / wants / investment). Each later year carries last
  year's rupees forward and splits only the **raise**, by that person's
  increment split, which tilts toward investing. A year with an income drop
  scales every bucket down proportionally. A zero-income year gets no row.
  Projects to the current year + 3 at `forward_increment_pct`. The splits live
  in `config.py` (`DEFAULT_BASE_SPLIT`, `PROFILE_INCREMENT_SPLITS`), and the
  Budget page prints the active person's.
- **Goal** for a year = its investment amount × target % per category. A
  saved allocation carries forward until a newer year replaces it.
- **Catch-up** = the lump sum that, invested today, erases every *past* year's
  shortfall (grown at the expected return). The current year's gap is "left to
  go", not catch-up. Overshooting is fine.
- **Estimated value** = contributions compounded at the expected return, plus
  the emergency fund (the amount held, or the derived target until one is
  entered), plus any opening corpus. It's a projection, not a valuation.
- **One rate everywhere:** `expected_return_pct` in `config.yaml` is the single
  growth rate for estimated value, corpus, and catch-up. Remove it to fall back
  to per-category `EXPECTED_RETURNS` in `config.py`.
- **Emergency fund target** = `EMERGENCY_FUND_MONTHS` (3) × current monthly
  salary (the latest month entered up to today; bonus and other left out).
- **Opening corpus** is money invested before tracking began. It's assumed
  invested at the start of your first tracked year and counts toward invested
  and estimated value. It never touches the budget, goal, or catch-up.
- **Health nudges** appear only when something needs a look: no income this
  year, investing under half the elapsed-year pace, no emergency fund recorded,
  or this year's mix ≥ 15 points off target.
- **House fund** = the *liquid* corpus today (contributions in
  `LIQUID_CATEGORIES` grown at the return, plus the opening corpus unless
  unticked; EPF/PPF/NPS and the emergency fund are left out), grown each year,
  plus a yearly pace that grows too. The pace defaults to this year's liquid
  contributions scaled up to a full year, so it reads low if Investments are
  behind. Return, pace, pace growth and horizon are live inputs; nothing is
  saved. Registration isn't subtracted.

## Code layout

Flat modules at the root:

| Module | Role |
|---|---|
| `config.py` | palette, model constants, labels (the one place for numbers) |
| `models.py` | pydantic schemas for the YAML files |
| `storage.py` | CSV/YAML I/O, validation, atomic saves |
| `audit.py` | the `changes.jsonl` log |
| `compute.py` | the financial model, pure functions |
| `ui.py` | Streamlit helpers: formatting, tiles, theme, save messages |
| `views/` | the five pages |
| `scripts/` | data-folder scaffold, Zerodha importer and summary |
| `tests/` | ₹-exact model tests + headless page renders (`AppTest`) |

## Non-goals

Live prices, broker APIs, market-value tracking, auth, sync, mobile, cloud.
Local only.
