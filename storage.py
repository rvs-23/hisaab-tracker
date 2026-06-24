"""Read/write the plain-file data store (YAML + CSV).

The data folder is the database: it lives outside the repo (path in .env) and
every loader re-reads from disk — no caching anywhere. The numeric history is
three tidy CSVs, all keyed by (year, profile):

  income.csv         monthly rows per person — salary + bonus + other
  contributions.csv  what was actually invested, per person/year/category
  targets.csv        per-year target-allocation overrides (optional)

The budget (needs/wants/investment) and the emergency fund (6 months of needs)
are *derived* from income, not stored.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from config import INCOME_COMPONENTS
from models import Config, Profile

REPO_ROOT = Path(__file__).resolve().parent  # this module sits at the repo root

# Income drives everything; the budget split is derived (see compute.py).
# Entered monthly (month 1–12); compute aggregates to yearly. `job_change` is a
# per-year 0/1 flag (repeated across the year's rows) marking a job switch.
INCOME_COLUMNS = ["profile", "year", "month", *INCOME_COMPONENTS, "job_change"]
CONTRIB_COLUMNS = ["year", "profile", "category", "amount", "notes"]
TARGETS_COLUMNS = ["profile", "year", "category", "pct"]


def data_dir() -> Path:
    """Resolve DATA_DIR from .env at the repo root (parsed by hand to avoid a dependency)."""
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        raise FileNotFoundError("missing .env — copy .env.example and set DATA_DIR")
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line.startswith("DATA_DIR"):
            _, _, raw = line.partition("=")
            path = Path(raw.strip().strip("\"'")).expanduser()
            if not path.is_dir():
                raise FileNotFoundError(f"DATA_DIR does not exist: {path}")
            return path
    raise KeyError("DATA_DIR not set in .env")


def load_config(root: Path) -> Config:
    with open(root / "config.yaml") as f:
        return Config(**yaml.safe_load(f))


def load_profiles(root: Path, config: Config) -> list[Profile]:
    files = sorted((root / "profiles").glob("*.yaml"))
    if not files:
        raise FileNotFoundError(f"no profile YAMLs found in {root / 'profiles'}")
    profiles = []
    for file in files:
        with open(file) as f:
            profile = Profile(key=file.stem, **yaml.safe_load(f))
        unknown = set(profile.default_target) - set(config.categories)
        if unknown:
            raise ValueError(
                f"{file.name}: default_target uses categories not in config.yaml: {sorted(unknown)}"
            )
        profiles.append(profile)
    return profiles


# --- targets (per-year overrides) -----------------------------------------

def load_targets(root: Path, config: Config, profiles: list[Profile]) -> pd.DataFrame:
    path = root / "targets.csv"
    if not path.exists():
        return pd.DataFrame(columns=TARGETS_COLUMNS)
    df = pd.read_csv(path)
    validate_targets(df, config, profiles)
    return df


def validate_targets(df: pd.DataFrame, config: Config, profiles: list[Profile]) -> None:
    _check_columns(df, TARGETS_COLUMNS, "targets.csv")
    if df.empty:
        return
    _check_profiles(df, profiles, "targets.csv")
    bad_cat = set(df["category"].dropna()) - set(config.categories)
    if bad_cat:
        raise ValueError(f"targets.csv uses categories not in config.yaml: {sorted(bad_cat)}")
    _check_numeric(df, ["year", "pct"], "targets.csv")
    if (df["pct"] < 0).any() or (df["pct"] > 100).any():
        raise ValueError("targets.csv has pct outside 0–100")
    _check_no_duplicates(df, ["profile", "year", "category"], "targets.csv")
    for (profile, year), g in df.groupby(["profile", "year"]):
        total = g["pct"].sum()
        if abs(total - 100) > 0.01:
            raise ValueError(f"targets.csv {profile} {int(year)}: pct must sum to 100, got {total}")


# --- income ---------------------------------------------------------------

def load_income(root: Path, profiles: list[Profile]) -> pd.DataFrame:
    df = _read_optional(root / "income.csv", INCOME_COLUMNS)
    if "job_change" not in df.columns:  # tolerate older files without the flag
        df["job_change"] = 0
    validate_income(df, profiles)
    return df.sort_values(["profile", "year"]).reset_index(drop=True)


def validate_income(df: pd.DataFrame, profiles: list[Profile]) -> None:
    _check_columns(df, INCOME_COLUMNS, "income.csv")
    _check_profiles(df, profiles, "income.csv")
    if df.empty:
        return
    _check_numeric(df, ["year", "month", *INCOME_COMPONENTS], "income.csv")
    if df["year"].isna().any() or df["salary"].isna().any():
        raise ValueError("income.csv has rows with a missing year or salary")
    if not df["month"].between(1, 12).all():
        raise ValueError("income.csv has rows with month outside 1–12")
    _check_non_negative(df, INCOME_COMPONENTS, "income.csv")
    _check_no_duplicates(df, ["profile", "year", "month"], "income.csv")


# --- contributions --------------------------------------------------------

def load_contributions(root: Path, config: Config, profiles: list[Profile]) -> pd.DataFrame:
    df = _read_optional(root / "contributions.csv", CONTRIB_COLUMNS)
    validate_contributions(df, config, profiles)
    return df


def validate_contributions(df: pd.DataFrame, config: Config, profiles: list[Profile]) -> None:
    _check_columns(df, CONTRIB_COLUMNS, "contributions.csv")
    _check_profiles(df, profiles, "contributions.csv")
    if df.empty:
        return
    _check_numeric(df, ["year", "amount"], "contributions.csv")
    if df["year"].isna().any() or df["amount"].isna().any():
        raise ValueError("contributions.csv has rows with a missing year or amount")
    bad = set(df["category"].dropna()) - set(config.categories)
    if bad:
        raise ValueError(f"contributions.csv uses categories not in config.yaml: {sorted(bad)}")
    _check_non_negative(df, ["amount"], "contributions.csv")


# --- savers ---------------------------------------------------------------

def save_income(root: Path, df: pd.DataFrame) -> None:
    df.sort_values(["profile", "year", "month"]).to_csv(root / "income.csv", index=False)


def save_contributions(root: Path, df: pd.DataFrame) -> None:
    df.sort_values(["year", "profile", "category"]).to_csv(root / "contributions.csv", index=False)


def save_targets(root: Path, df: pd.DataFrame) -> None:
    df.sort_values(["profile", "year", "category"]).to_csv(root / "targets.csv", index=False)


# --- helpers --------------------------------------------------------------

def _read_optional(path: Path, columns: list[str]) -> pd.DataFrame:
    """Reads a CSV, or returns an empty frame with ``columns`` if it's absent.

    A fresh data folder only needs ``config.yaml`` + ``profiles/``; the history
    CSVs are created on first save, so a missing one means "nothing entered yet".
    """
    if not path.exists():
        return pd.DataFrame(columns=columns)
    return pd.read_csv(path)


def _check_columns(df: pd.DataFrame, expected: list[str], filename: str) -> None:
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise ValueError(f"{filename} is missing columns: {missing}")


def _check_profiles(df: pd.DataFrame, profiles: list[Profile], filename: str) -> None:
    bad = set(df["profile"].dropna()) - {p.key for p in profiles}
    if bad:
        raise ValueError(f"{filename} has unknown profiles: {sorted(bad)}")


def _check_numeric(df: pd.DataFrame, columns: list[str], filename: str) -> None:
    """Rejects hand-edited cells that aren't numbers (e.g. ``amount = "abc"``).

    A value that won't coerce becomes NaN; flag any column where coercion turns a
    present value into NaN, so a typo fails loudly instead of silently passing the
    non-negative check.
    """
    for col in columns:
        coerced = pd.to_numeric(df[col], errors="coerce")
        if (coerced.isna() & df[col].notna()).any():
            raise ValueError(f"{filename} has non-numeric values in {col}")


def _check_non_negative(df: pd.DataFrame, columns: list[str], filename: str) -> None:
    for col in columns:
        if (pd.to_numeric(df[col], errors="coerce") < 0).any():
            raise ValueError(f"{filename} has negative values in {col}")


def _check_no_duplicates(df: pd.DataFrame, keys: list[str], filename: str) -> None:
    dups = df[df.duplicated(keys, keep=False)]
    if not dups.empty:
        sample = dups[keys].drop_duplicates().head(3).to_dict("records")
        raise ValueError(f"{filename} has duplicate rows for {keys}: {sample}")
