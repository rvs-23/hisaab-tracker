"""Import a Zerodha equity/MF tradebook CSV as one contribution row.

Zerodha's tradebook export (Console → Reports → Tradebook) has one row per
fill, with (at least) these columns: ``symbol, isin, trade_date, exchange,
segment, series, trade_type, quantity, price``. This script collapses a
year's worth of fills into the single number the tracker wants — the net
rupees actually put in — and writes it as one ``contributions.csv`` row via
the normal storage loaders/validators/savers, so it rides the audit log like
any hand-entered save.

Usage::

    uv run python scripts/import_tradebook.py <csv-path> --profile rv --year 2024
    uv run python scripts/import_tradebook.py <csv-path> --profile rv --year 2024 \\
        --category indian_stocks --replace
    uv run python scripts/import_tradebook.py <csv-path> --profile rv --year 2024 --dry-run

The category is auto-detected from the tradebook's ``segment`` column (``EQ``
→ ``indian_stocks``, ``MF`` → ``mfs``); pass ``--category`` to override (it
must be one of ``config.yaml``'s categories). NET = gross buys − gross sells,
rounded to the rupee, for rows whose ``trade_date`` falls in ``--year`` only —
rows from any other year in the file are counted and reported, never
imported. A negative NET (net sells) is refused. Importing a
(profile, year, category) that already has a contribution row is refused
unless ``--replace``, which swaps just that one row.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:  # so `python scripts/import_tradebook.py` finds storage.py
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

import storage

REQUIRED_COLUMNS = ["symbol", "isin", "trade_date", "exchange", "segment", "series",
                    "trade_type", "quantity", "price"]

# Zerodha's tradebook segment → this tracker's asset-class category.
SEGMENT_CATEGORY = {"EQ": "indian_stocks", "MF": "mfs"}


def read_tradebook(csv_path: Path) -> pd.DataFrame:
    """Reads a Zerodha tradebook CSV, failing loudly if it's missing columns."""
    df = pd.read_csv(csv_path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{csv_path} is missing expected tradebook columns: {missing}")
    return df


def year_totals(df: pd.DataFrame, year: int) -> tuple[float, float, float, dict[int, int]]:
    """Splits a tradebook into one year's gross buys/sells/net, plus a count
    of rows in every *other* year present (reported, never imported).

    Returns:
        A ``(gross_buys, gross_sells, net, other_year_counts)`` tuple, all
        rupee figures rounded to the rupee. ``other_year_counts`` maps year
        to row count, for years other than ``year`` found in the file.
    """
    trade_year = pd.to_datetime(df["trade_date"]).dt.year
    in_year = df[trade_year == year]
    other_counts = trade_year[trade_year != year].value_counts().sort_index()
    other_year_counts = {int(y): int(n) for y, n in other_counts.items()}

    value = in_year["quantity"].astype(float) * in_year["price"].astype(float)
    side = in_year["trade_type"].astype(str).str.strip().str.lower()
    gross_buys = round(float(value[side == "buy"].sum()))
    gross_sells = round(float(value[side == "sell"].sum()))
    net = gross_buys - gross_sells
    return gross_buys, gross_sells, net, other_year_counts


def detect_category(df_in_year: pd.DataFrame, override: str | None,
                    known_categories: list[str]) -> str:
    """Resolves the contribution category for the imported rows.

    ``override`` (``--category``) wins outright, provided it is one of
    ``known_categories`` (config.yaml). Otherwise the category is inferred
    from the tradebook's own ``segment`` column via ``SEGMENT_CATEGORY``: this
    only works when every in-year row maps to the same category — an empty or
    mixed set of segments is an error asking for ``--category`` explicitly.
    """
    if override is not None:
        if override not in known_categories:
            raise ValueError(
                f"--category {override!r} is not in config.yaml's categories: {known_categories}"
            )
        return override

    segments = set(df_in_year["segment"].dropna().astype(str).str.strip().str.upper())
    mapped = {SEGMENT_CATEGORY[s] for s in segments if s in SEGMENT_CATEGORY}
    if len(mapped) == 1:
        return mapped.pop()
    if not mapped:
        raise ValueError(
            f"could not auto-detect a category from segment(s) {sorted(segments)} — pass --category"
        )
    raise ValueError(
        f"tradebook mixes categories via segments {sorted(segments)} — pass --category to pick one"
    )


def build_notes(gross_buys: float, gross_sells: float, today: dt.date | None = None) -> str:
    """Returns the provenance note recorded in the contribution row."""
    today = today or dt.date.today()
    return (f"Zerodha tradebook net (buys {gross_buys:,.0f} − sells {gross_sells:,.0f}), "
            f"imported {today.isoformat()}")


def existing_row(contributions: pd.DataFrame, profile: str, year: int,
                 category: str) -> pd.Series | None:
    """Returns the existing contribution row for (profile, year, category), or None."""
    match = contributions[
        (contributions["profile"] == profile) & (contributions["year"] == year)
        & (contributions["category"] == category)
    ]
    return match.iloc[0] if not match.empty else None


def merged_contributions(contributions: pd.DataFrame, profile: str, year: int,
                         category: str, amount: float, notes: str) -> pd.DataFrame:
    """Returns contributions.csv with the (profile, year, category) row set to
    ``amount``/``notes`` — replacing it if present, else appending it."""
    others = contributions[
        ~((contributions["profile"] == profile) & (contributions["year"] == year)
          & (contributions["category"] == category))
    ]
    new_row = pd.DataFrame([{"year": year, "profile": profile, "category": category,
                             "amount": amount, "notes": notes}])
    return pd.concat([others, new_row], ignore_index=True)[storage.CONTRIB_COLUMNS]


def run(csv_path: Path, profile_key: str, year: int, category_override: str | None,
       replace: bool, dry_run: bool, root: Path | None = None) -> int:
    """Runs the import end to end; returns a process exit code (0 = success).

    Args:
        root: Data folder to read/write. Defaults to ``storage.data_dir()`` —
            tests pass a tmp path instead so real data is never touched.
    """
    root = root or storage.data_dir()
    config = storage.load_config(root)
    profiles = storage.load_profiles(root, config)
    profile_keys = {p.key for p in profiles}
    if profile_key not in profile_keys:
        print(f"Unknown profile {profile_key!r} — known profiles: {sorted(profile_keys)}")
        return 1

    df = read_tradebook(csv_path)
    trade_year = pd.to_datetime(df["trade_date"]).dt.year
    in_year = df[trade_year == year]

    try:
        category = detect_category(in_year, category_override, config.categories)
    except ValueError as exc:
        print(f"Refusing: {exc}")
        return 1

    gross_buys, gross_sells, net, other_years = year_totals(df, year)
    if other_years:
        print(f"Other years found in the file (ignored): {other_years}")
    print(f"{profile_key} {year} {category}: gross buys ₹{gross_buys:,.0f}, "
          f"gross sells ₹{gross_sells:,.0f}, NET ₹{net:,.0f}")

    if net < 0:
        print(f"Refusing: NET is negative (₹{net:,.0f}) — sells exceeded buys in {year}.")
        return 1

    contributions = storage.load_contributions(root, config, profiles)
    existing = existing_row(contributions, profile_key, year, category)
    if existing is not None and not replace:
        print(
            f"Refusing: a contribution row already exists for "
            f"(profile={profile_key}, year={year}, category={category}): ₹{existing['amount']:,.0f}. "
            "Pass --replace to overwrite it."
        )
        return 1

    notes = build_notes(gross_buys, gross_sells)
    combined = merged_contributions(contributions, profile_key, year, category, net, notes)

    action = "replace" if existing is not None else "add"
    if dry_run:
        print(f"DRY RUN — would {action} row: year={year} profile={profile_key} "
              f"category={category} amount={net} notes={notes!r}")
        print("DRY RUN — nothing written.")
        return 0

    storage.validate_contributions(combined, config, profiles)
    storage.save_contributions(root, combined)
    print(f"Wrote ({action}): year={year} profile={profile_key} category={category} "
          f"amount={net} notes={notes!r}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import a Zerodha tradebook CSV as one contribution row (net buys − sells).",
    )
    parser.add_argument("csv_path", type=Path, help="Path to the Zerodha tradebook CSV export.")
    parser.add_argument("--profile", required=True, help="Profile key (matches profiles/<key>.yaml).")
    parser.add_argument("--year", required=True, type=int, help="Only trades in this year are imported.")
    parser.add_argument("--category", default=None,
                        help="Override the auto-detected category (must be in config.yaml).")
    parser.add_argument("--replace", action="store_true",
                        help="Overwrite an existing (profile, year, category) row.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be written without writing it.")
    args = parser.parse_args(argv)
    return run(args.csv_path, args.profile, args.year, args.category, args.replace, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
