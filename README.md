# rv-finance-tracker

Minimal, local, file-based personal financial planner for two people. Runs on one Mac via Streamlit. No server, no database, no auth, no live market data.

## Run

```sh
uv sync
uv run streamlit run app.py
```

Tests: `uv run pytest`

## Data

The data folder is the database. It lives **outside the repo** (iCloud Drive, so it's backed up automatically) and is referenced by `DATA_DIR` in `.env` (copy `.env.example`). All values are user-stated as-of a date; USD converts at the rate you set in `config.yaml`.

```
FinanceData/
  config.yaml        # usd_inr_rate, categories, target_mix
  profiles/
    rv.yaml          # salary, split %, projection params (filename = profile key)
    partner.yaml
  holdings.csv       # date,profile,instrument,category,currency,value,notes
  income.csv         # date,profile,source,amount,notes
```

`holdings.csv` is **append-only history**: each update adds rows with a new date (the "Start a new snapshot" button on the Update Data page copies the latest rows forward). "Current" state is each profile's rows at its own most recent date; the full file drives the net-worth-over-time chart. Backfilling old data (e.g. from the 2023+ Excel) is just adding rows with old dates.

Everything is editable in-app (Update Data page) or directly in any text editor / Numbers — the app re-reads files on every refresh and never caches.

## Pages

- **Dashboard** — net worth now (per person + household), growth over time
- **Allocation** — current value and % by category, per person or combined
- **Plan vs Actual** — target mix (config) vs holdings, surplus/shortfall per category
- **Budget & Projection** — salary split (needs/wants/investment) and multi-year cumulative-invested projection
- **Income** — income log and monthly totals
- **Update Data** — edit holdings/income in a grid, start new snapshots

## Decisions (2026-06-11)

- Single Mac, no LAN/server setup — both users share the laptop
- Data folder in iCloud Drive (not Google Drive as the original spec said) — already syncing on this Mac, backup is the only need
- Fully historical from day one (Excel data since 2023 to be backfilled later)
- Fresh schema, not a port of the Excel layout
- Categories: zerodha_equity, zerodha_mf, us_equity, ppf, nps, fd, crypto, emergency_fund, cash

## Roadmap (not built yet)

1. Zerodha Console holdings-export importer (needs one sample CSV)
2. Backfill 2023+ history from the old Excel

## Non-goals

Live prices/FX, broker APIs, auth, multi-device sync, mobile, expense tracking, notifications, cloud hosting.
