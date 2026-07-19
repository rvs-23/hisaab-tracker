# Personal Finances Tracker

A local Streamlit app for two people that replaces a finance-tracking Excel.
It answers one question — *did we invest what the plan said this year?* — so it
tracks **contributions vs goal**, never net worth. Income drives a derived
budget, a target allocation, and a planned-vs-actual comparison.

New here? **[docs/how-it-works.md](docs/how-it-works.md)** is the 5-minute,
no-jargon guide.

## Run it

`app.py` is the entry point (pages via `st.navigation`):

```sh
uv sync
cp .env.example .env          # set DATA_DIR to your data folder
uv run streamlit run app.py   # http://localhost:8501
```

Python ≥ 3.14. Tests: `uv run pytest`.

## Data

**Everything is entered by hand** — no bank, broker, or statement import. Data
lives in a plain CSV/YAML folder outside the repo (`DATA_DIR` in `.env`, never
committed), re-read from disk on every refresh. The minimum is `config.yaml`
(`categories`) plus one `profiles/<key>.yaml` per person (`name, birth_year,
forward_increment_pct, default_target`; the filename stem is the profile key);
the history CSVs appear as you save. Scaffold a fresh folder with
`uv run python scripts/init_data_dir.py <path>`.

Every save **validates first** (numeric, non-negative — except income's
*other*, which may be negative — known categories/profiles, no duplicates, %s
sum to 100) and refuses bad input with a message. Every accepted save appends
one JSON line to **`changes.jsonl`** — an append-only audit log of exactly
which rows were added and removed.

Each page shows **one person at a time** via `?profile=<key>` (`rv` or
`cheeni`); set it once and it sticks across pages. Year pickers are locked to
**2022 → now**.

## Pages

**Dashboard** and **Budget** are read-only — they recompute from what you enter
elsewhere. Dashboard opens with four lifetime tiles, then the year-on-year
journey (bars: income and the planned goal; line: what you actually
invested), the net-worth projection, cumulative allocation by category
(stacked by the year each rupee went in), and the catch-up callout. A quiet
**Adjustments** expander at the bottom holds one-off audited figures —
currently just **opening corpus** (see below). Budget shows how income splits
and how the investment slice grows.

The two write pages:

- **Income** → `income.csv`. Pick a year, fill 12 months of
  `salary / bonus / other` (RSU vesting or a maturing FD goes under *other*;
  *other* may also go negative, e.g. a tax payment or clawback); tick **Job
  change** if you switched jobs. A new year pre-fills last year's monthly
  salary; *Copy January down* fills the rest. Everything else derives from
  this.
- **Actuals** → `contributions.csv` and `targets.csv`. One row per instrument
  for the picked year — what you actually invested, shown against the plan and
  the derived emergency-fund target. A read-only "Target allocation" table
  shows the active %-mix; its editor (Save enables only at 100%, ₹/year and
  ₹/month live) sits in an expander. A saved year carries forward until
  replaced. Saves never touch other people, other years, or the other file.

## The numbers

- **Budget** is derived, never stored: the first earning year splits income
  **50/15/35** (needs/wants/investment); each later year splits only the
  **increment 35/15/50**, so raises flow to investing. A zero-income year gets
  no budget row; an income drop scales the split down proportionally. Projects
  to current + 3 at `forward_increment_pct`.
- **Goal** for a year = its investment amount × target %, per category.
- **Potential net worth** = contributions compounded at conservative
  per-category returns (`EXPECTED_RETURNS`) plus the emergency fund (what you
  actually hold — or, until entered, the derived target of 4 months of needs +
  wants) plus any **opening corpus**. A projection, not a valuation.
- **Opening corpus** (optional, set in Dashboard → Adjustments) is money
  invested before tracking began. It's assumed invested at the start of your
  first tracked year and grown at your allocation-weighted expected return; it
  counts toward "Invested till date" and net worth, but never touches the
  budget, goals, catch-up, or plan-vs-actual.
- **Catch-up** = the lump sum, invested today, that pulls you level with every
  missed year (shortfalls grown at expected returns; the current year counts
  only its elapsed fraction; overshooting is fine).

## Layout

Flat: `app.py` (entry) · `config.py` (palette + model constants) · `models.py`
(pydantic YAML schemas) · `storage.py` (CSV/YAML I/O + validation) · `audit.py`
(save log) · `compute.py` (pure financial model) · `ui.py` (Streamlit helpers)
· `views/` (the four pages) · `tests/` (golden + headless render tests).

## Non-goals

Live prices/FX, broker APIs, market-value tracking, auth, multi-device sync,
mobile, cloud. Local only — no server, no database.
