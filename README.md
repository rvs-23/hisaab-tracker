# Personal Finances Tracker

A local Streamlit app for two people that replaces a finance-tracking Excel. It
answers one question — *did we invest what the plan said this year?* — so it
tracks **contributions vs goal**, not net worth. Income drives a derived budget,
a target allocation, and a planned-vs-actual comparison.

## Run it

**`app.py` is the entry point** — it defines the pages via `st.navigation`:

```sh
uv sync
cp .env.example .env          # set DATA_DIR to your data folder
uv run streamlit run app.py   # http://localhost:8501
```

Requires Python ≥ 3.14. Tests: `uv run pytest`.

## Entering data

**All data is entered by hand** — there is no bank, broker, or statement import.
You type it through the app (or edit the CSVs directly); each page edits its own
files in place and the app re-reads from disk on every refresh. Data lives in a
plain **CSV/YAML folder outside the repo** (`DATA_DIR` in `.env`, never
committed). The minimum to start is a folder with `config.yaml` and a `profiles/`
directory — the CSVs are created as you save.

Each page shows **one person at a time** via the `?profile=<key>` URL — `rv`
(Brownie) or `cheeni`. Set it once and it sticks across pages (no on-page
switcher). Work down the sidebar:

1. **Income** — pick a year, fill the 12 months (`salary`, `bonus`, `other`; put
   RSU/FD/RD under *other*), tick *job change* if you switched jobs. Year pickers
   are locked to **2022 → now** (2022 is a zero baseline; tracking starts 2023).
   Everything else derives from this.
2. **Budget** *(read-only)* — how income splits into needs/wants/investment, and
   how the investment slice grows. Change it on Income.
3. **Allocation** — set the **%** per instrument (sum to 100); ₹/year and ₹/month
   follow from that year's investment.
4. **Actuals** — record what you **actually** invested per instrument; see
   planned vs actual, % of goal, and the derived emergency-fund target.
5. **Dashboard** *(read-only)* — the consolidated journey: earning/investing
   trajectory, lifetime cards, a **catch-up** figure, a net-worth projection, and
   planned-vs-actual per year.

The files (all plain text, hand-editable):

| File | Shape |
|------|-------|
| `income.csv` | `profile, year, month (1–12), salary, bonus, other, job_change` — monthly rows; `job_change` a per-year 0/1 flag |
| `targets.csv` | `profile, year, category, pct` — optional per-year allocation overrides (sum to 100; else `default_target`) |
| `contributions.csv` | `year, profile, category, amount, notes` — what was actually invested |
| `config.yaml` | `usd_inr_rate, usd_inr_as_of, categories` |
| `profiles/<key>.yaml` | `name, birth_year, forward_increment_pct, default_target`; the filename stem is the `profile` key |

## How the numbers work

- **Budget** is derived from income, never stored: the anchor (earliest) year
  splits income **50/30/20**; each later year splits only the **increment 20/30/50**,
  so raises flow to investing. Projects to *current + 3* at `forward_increment_pct`.
- **Goal** for a year = its investment amount split by the target:
  `expected[cat] = investment × target%`.
- **Potential net worth** — contributions compounded at conservative per-category
  returns (`EXPECTED_RETURNS`), plus the **emergency fund** (derived: 6 months of
  needs). A projection, not a live valuation.
- **Catch-up** = the lump sum to invest *today* to pull level with the plan (each
  year's shortfall grown to today at expected returns; overshooting is fine).
- `storage.py` validates every file on load and rejects bad hand-edits.

## Layout

Flat — modules at the root, pages in `views/`:

- **`app.py`** — entry point: page config, logo, `st.navigation`.
- **`config.py`** palette + model constants · **`models.py`** pydantic YAML schemas.
- **`storage.py`** CSV/YAML load/save + validation · **`compute.py`** the financial
  model as pure functions.
- **`ui.py`** Streamlit helpers (`load_all`, `metric_tile`, …) · **`views/*.py`**
  the five pages · **`tests/`** golden + headless render tests.

## Non-goals

Live prices/FX, broker APIs, net-worth/market-value tracking, auth, multi-device
sync, mobile, cloud. Local only — no server, no database, no live data.
