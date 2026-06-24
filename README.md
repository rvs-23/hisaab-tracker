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
You type it through the app (or edit the CSVs directly); the app re-reads from
disk on every refresh. Data lives in a plain **CSV/YAML folder outside the repo**
(`DATA_DIR` in `.env`, never committed). The minimum to start is `config.yaml`
(`usd_inr_rate, usd_inr_as_of, categories`) and a `profiles/<key>.yaml` per person
(`name, birth_year, forward_increment_pct, default_target`; the filename stem is
the `profile` key) — the history CSVs are created as you save.

Each page shows **one person at a time** via the `?profile=<key>` URL — `rv`
(Brownie) or `cheeni`. Set it once and it sticks across pages (no on-page switcher).

### Read-only pages

Nothing to fill; they recompute from what you enter on the write pages.

- **Budget** — how income splits into needs / wants / investment, and how the
  investment slice grows each year.
- **Dashboard** — the consolidated journey: earning/investing trajectory, lifetime
  cards, a **catch-up** figure, a net-worth projection, and planned-vs-actual per year.

### Write pages

**Income**, **Allocation**, **Actuals** — the three places you type things in.
Every **Save validates first** (numeric, non-negative, known categories/profiles,
no duplicate keys, %s sum to 100) and refuses bad input with a message rather than
writing it. Year pickers everywhere are locked to **2022 → now** (2022 is a zero
baseline; real tracking starts 2023).

### The write pages, step by step

**Income** → stores `income.csv` (`profile, year, month, salary, bonus, other, job_change`)
1. Pick a year, then fill the 12 months: `salary`, `bonus`, `other` (put RSU vesting
   or an FD/RD maturing under *other*). The **Total** column updates live as you type.
2. *Fallbacks:* a brand-new year pre-fills each month with last year's monthly salary;
   **Copy January down** fills all 12 months from January.
3. Tick **Job change this year?** if you switched jobs (a per-year flag).
4. Save writes one row per month. Everything else — budget, goal, emergency fund —
   derives from this.

**Allocation** → stores `targets.csv` (`profile, year, category, pct`)
1. Pick a year, set the **%** per instrument. **Save stays disabled until they sum
   to 100**; ₹/year and ₹/month fill in live from that year's investment amount.
2. *Fallback:* with no override, the profile's `default_target` applies; a saved year
   **carries forward** until you set a newer one.
3. Save writes only the per-year override rows (everything else stays on the default).

**Actuals** → stores `contributions.csv` (`year, profile, category, amount, notes`)
1. Pick a year; add one row per instrument with the **amount** you actually invested.
2. See planned vs actual, % of goal, and the year's emergency-fund target (derived:
   6 months of needs — nothing to enter for it).
3. *Fault tolerance:* the editor shows only the active person; on save your rows merge
   back with the **other profile's rows left untouched**.

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
