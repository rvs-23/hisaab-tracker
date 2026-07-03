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

Every save **validates first** (numeric, non-negative, known
categories/profiles, no duplicates, %s sum to 100) and refuses bad input with a
message. Every accepted save appends one JSON line to **`changes.jsonl`** — an
append-only audit log of exactly which rows were added and removed.

Each page shows **one person at a time** via `?profile=<key>` (`rv` or
`cheeni`); set it once and it sticks across pages. Year pickers are locked to
**2022 → now**.

## Pages

**Dashboard** and **Budget** are read-only — they recompute from what you enter
elsewhere. Dashboard is the consolidated journey: the catch-up figure,
earning/investing trajectory, lifetime cards, a net-worth projection, and
planned-vs-actual per year. Budget shows how income splits and how the
investment slice grows.

The three write pages:

- **Income** → `income.csv`. Pick a year, fill 12 months of
  `salary / bonus / other` (RSU vesting or a maturing FD goes under *other*);
  tick **Job change** if you switched jobs. A new year pre-fills last year's
  monthly salary; *Copy January down* fills the rest. Everything else derives
  from this.
- **Allocation** → `targets.csv`. Set the % per instrument; Save enables only
  at 100%, with ₹/year and ₹/month filling in live. A saved year carries
  forward until replaced; until then the profile's `default_target` applies.
- **Actuals** → `contributions.csv`. One row per instrument for the picked
  year — what you actually invested, shown against the plan and the derived
  emergency-fund target. Saves never touch other people or other years.

## The numbers

- **Budget** is derived, never stored: the first earning year splits income
  **50/30/20** (needs/wants/investment); each later year splits only the
  **increment 20/30/50**, so raises flow to investing. A zero-income year gets
  no budget row; an income drop scales the split down proportionally. Projects
  to current + 3 at `forward_increment_pct`.
- **Goal** for a year = its investment amount × target %, per category.
- **Potential net worth** = contributions compounded at conservative
  per-category returns (`EXPECTED_RETURNS`) plus the emergency fund (6 months
  of needs). A projection, not a valuation.
- **Catch-up** = the lump sum, invested today, that pulls you level with every
  missed year (shortfalls grown at expected returns; overshooting is fine).

## Layout

Flat: `app.py` (entry) · `config.py` (palette + model constants) · `models.py`
(pydantic YAML schemas) · `storage.py` (CSV/YAML I/O + validation) · `audit.py`
(save log) · `compute.py` (pure financial model) · `ui.py` (Streamlit helpers)
· `views/` (the five pages) · `tests/` (golden + headless render tests).

## Non-goals

Live prices/FX, broker APIs, market-value tracking, auth, multi-device sync,
mobile, cloud. Local only — no server, no database.
