"""Summarise how much went in, from any number of Zerodha tradebook exports.

Read-only: it prints a table and writes nothing. Use it to answer "how much
did we invest in X" before deciding what to record (by hand on Investments, or
with ``import_tradebook.py``).

Takes Console → Reports → Tradebook CSV exports. Equity and mutual-fund
files can be mixed, and overlapping date ranges are fine: fills are
de-duplicated on ``trade_id`` when the column is present.

Usage::

    uv run python scripts/zerodha_summary.py ~/Downloads/tradebook-*.csv
    uv run python scripts/zerodha_summary.py eq.csv mf.csv --year 2026
    uv run python scripts/zerodha_summary.py eq.csv --from 2026-08-01 --to 2026-10-31 --by month
    uv run python scripts/zerodha_summary.py eq.csv --year 2026 --by symbol

Net = buys − sells at fill price (quantity × price), so charges are excluded.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

NEEDED = ["symbol", "trade_date", "segment", "trade_type", "quantity", "price"]
SEGMENT_NAMES = {"EQ": "Stocks", "MF": "Mutual funds", "FO": "F&O", "CDS": "Currency", "COM": "Commodity"}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lower-cases headers and swaps spaces for underscores ("Trade Date" → "trade_date")."""
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def read_one(path: Path) -> pd.DataFrame:
    """Reads one tradebook CSV into the normalised columns.

    Raises:
        ValueError: If a needed column is missing.
    """
    df = _normalise_columns(pd.read_csv(path))
    missing = [c for c in NEEDED if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing tradebook columns {missing}")
    return df.dropna(subset=["symbol", "trade_date"])


def load_tradebooks(paths: list[Path]) -> tuple[pd.DataFrame, int]:
    """Reads and combines exports, dropping fills seen in more than one file.

    Returns:
        ``(fills, duplicates_dropped)``. ``fills`` gains a parsed ``date``, an
        upper-cased ``segment``, and a signed ``value`` (buys +, sells −).
    """
    df = pd.concat([read_one(p) for p in paths], ignore_index=True)
    before = len(df)
    if "trade_id" in df.columns:
        df = df.drop_duplicates(subset=["trade_id", "segment", "symbol", "trade_type"])
    dropped = before - len(df)
    df["date"] = pd.to_datetime(df["trade_date"]).dt.date
    df["segment"] = df["segment"].astype(str).str.strip().str.upper()
    side = df["trade_type"].astype(str).str.strip().str.lower()
    gross = df["quantity"].astype(float) * df["price"].astype(float)
    df["value"] = gross.where(side == "buy", -gross)
    return df, dropped


def summarise(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """Buys, sells and net per period (or symbol) and segment.

    Args:
        by: ``year``, ``month`` or ``symbol``.
    """
    key = {
        "year": df["date"].map(lambda d: str(d.year)),
        "month": df["date"].map(lambda d: f"{d:%Y-%m}"),
        "symbol": df["symbol"].astype(str),
    }[by]
    g = df.assign(key=key, buys=df["value"].clip(lower=0), sells=-df["value"].clip(upper=0))
    out = g.groupby(["key", "segment"], as_index=False)[["buys", "sells", "value"]].sum()
    out = out.rename(columns={"key": by, "value": "net"})
    out["segment"] = out["segment"].map(lambda s: SEGMENT_NAMES.get(s, s))
    return out.sort_values([by, "segment"]).reset_index(drop=True)


def _print_table(table: pd.DataFrame) -> None:
    shown = table.copy()
    for col in ("buys", "sells", "net"):
        shown[col] = shown[col].map(lambda v: f"₹{v:,.0f}")
    print(shown.to_string(index=False))
    totals = table.groupby("segment")[["buys", "sells", "net"]].sum()
    print("\nTotal by segment:")
    for seg, r in totals.iterrows():
        print(f"  {seg:<13} buys ₹{r.buys:,.0f}  sells ₹{r.sells:,.0f}  net ₹{r.net:,.0f}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarise Zerodha tradebook exports (read-only).")
    parser.add_argument("paths", type=Path, nargs="+", help="Tradebook CSV files.")
    parser.add_argument("--year", type=int, help="Only fills in this calendar year.")
    parser.add_argument("--from", dest="start", type=dt.date.fromisoformat, help="First date, YYYY-MM-DD.")
    parser.add_argument("--to", dest="end", type=dt.date.fromisoformat, help="Last date, YYYY-MM-DD.")
    parser.add_argument("--by", choices=["year", "month", "symbol"], default="year")
    args = parser.parse_args(argv)

    try:
        df, dropped = load_tradebooks(args.paths)
    except ValueError as exc:
        print(f"Refusing: {exc}")
        return 1
    if args.year:
        df = df[df["date"].map(lambda d: d.year) == args.year]
    if args.start:
        df = df[df["date"] >= args.start]
    if args.end:
        df = df[df["date"] <= args.end]
    if df.empty:
        print("No fills in that range.")
        return 0

    print(f"{len(df)} fills, {df['date'].min()} to {df['date'].max()}"
          + (f" ({dropped} duplicate fills across files dropped)" if dropped else ""))
    _print_table(summarise(df, args.by))
    return 0


if __name__ == "__main__":
    sys.exit(main())
