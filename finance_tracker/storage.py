"""Read/write the plain-file data store (YAML + CSV).

The data folder is the database: it lives outside the repo (path in .env) and
every loader re-reads from disk — no caching anywhere. The numeric history is
three tidy CSVs, all keyed by (year, profile):

  income.csv         one row per person per year — salary + bonus + other
  contributions.csv  what was actually invested, per person/year/category
  goals.csv          emergency-fund goal, per person/year
  targets.csv        per-year target-allocation overrides (optional)

The budget (needs/wants/investment) is *derived* from income, not stored.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from finance_tracker.models import Config, Profile

REPO_ROOT = Path(__file__).resolve().parent.parent

# Income drives everything; the budget split is derived (see compute.py).
# Entered monthly (month 1–12); compute aggregates to yearly. "other" catches
# anything that isn't salary/bonus/RSU, e.g. an FD or RD maturing.
INCOME_COLUMNS = ["profile", "year", "month", "salary", "bonus", "rsu", "other"]
INCOME_COMPONENTS = ["salary", "bonus", "rsu", "other"]
CONTRIB_COLUMNS = ["year", "profile", "category", "amount", "notes"]
GOALS_COLUMNS = ["year", "profile", "emergency_fund_goal"]
TARGETS_COLUMNS = ["profile", "year", "tier", "category", "pct"]
TIERS = {"short_term", "long_term"}


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
        for tier in (profile.default_target.short_term, profile.default_target.long_term):
            unknown = set(tier) - set(config.categories)
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
    bad_tier = set(df["tier"].dropna()) - TIERS
    if bad_tier:
        raise ValueError(f"targets.csv has unknown tiers: {sorted(bad_tier)} (use short_term/long_term)")
    bad_cat = set(df["category"].dropna()) - set(config.categories)
    if bad_cat:
        raise ValueError(f"targets.csv uses categories not in config.yaml: {sorted(bad_cat)}")
    for (profile, year, tier), g in df.groupby(["profile", "year", "tier"]):
        total = g["pct"].sum()
        if abs(total - 100) > 0.01:
            raise ValueError(
                f"targets.csv {profile} {int(year)} {tier}: pct must sum to 100, got {total}"
            )


# --- income ---------------------------------------------------------------

def load_income(root: Path, profiles: list[Profile]) -> pd.DataFrame:
    df = pd.read_csv(root / "income.csv")
    validate_income(df, profiles)
    return df.sort_values(["profile", "year"]).reset_index(drop=True)


def validate_income(df: pd.DataFrame, profiles: list[Profile]) -> None:
    _check_columns(df, INCOME_COLUMNS, "income.csv")
    _check_profiles(df, profiles, "income.csv")
    if df["year"].isna().any() or df["salary"].isna().any():
        raise ValueError("income.csv has rows with a missing year or salary")
    if not df.empty and not df["month"].between(1, 12).all():
        raise ValueError("income.csv has rows with month outside 1–12")


# --- contributions --------------------------------------------------------

def load_contributions(root: Path, config: Config, profiles: list[Profile]) -> pd.DataFrame:
    df = pd.read_csv(root / "contributions.csv")
    validate_contributions(df, config, profiles)
    return df


def validate_contributions(df: pd.DataFrame, config: Config, profiles: list[Profile]) -> None:
    _check_columns(df, CONTRIB_COLUMNS, "contributions.csv")
    _check_profiles(df, profiles, "contributions.csv")
    if df["year"].isna().any() or df["amount"].isna().any():
        raise ValueError("contributions.csv has rows with a missing year or amount")
    bad = set(df["category"].dropna()) - set(config.categories)
    if bad:
        raise ValueError(f"contributions.csv uses categories not in config.yaml: {sorted(bad)}")


# --- goals ----------------------------------------------------------------

def load_goals(root: Path, profiles: list[Profile]) -> pd.DataFrame:
    df = pd.read_csv(root / "goals.csv")
    validate_goals(df, profiles)
    return df


def validate_goals(df: pd.DataFrame, profiles: list[Profile]) -> None:
    _check_columns(df, GOALS_COLUMNS, "goals.csv")
    _check_profiles(df, profiles, "goals.csv")


# --- savers ---------------------------------------------------------------

def save_income(root: Path, df: pd.DataFrame) -> None:
    df.sort_values(["profile", "year", "month"]).to_csv(root / "income.csv", index=False)


def save_contributions(root: Path, df: pd.DataFrame) -> None:
    df.sort_values(["year", "profile", "category"]).to_csv(root / "contributions.csv", index=False)


def save_goals(root: Path, df: pd.DataFrame) -> None:
    df.sort_values(["year", "profile"]).to_csv(root / "goals.csv", index=False)


def save_targets(root: Path, df: pd.DataFrame) -> None:
    df.sort_values(["profile", "year", "tier", "category"]).to_csv(root / "targets.csv", index=False)


# --- helpers --------------------------------------------------------------

def _check_columns(df: pd.DataFrame, expected: list[str], filename: str) -> None:
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise ValueError(f"{filename} is missing columns: {missing}")


def _check_profiles(df: pd.DataFrame, profiles: list[Profile], filename: str) -> None:
    bad = set(df["profile"].dropna()) - {p.key for p in profiles}
    if bad:
        raise ValueError(f"{filename} has unknown profiles: {sorted(bad)}")
