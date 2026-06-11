"""Read/write the plain-file data store (YAML + CSV).

The data folder is the database: it lives outside the repo (path in .env)
and every loader re-reads from disk — no caching anywhere.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from finance_tracker.models import Config, Profile

REPO_ROOT = Path(__file__).resolve().parent.parent

HOLDINGS_COLUMNS = ["date", "profile", "instrument", "category", "currency", "value", "notes"]
INCOME_COLUMNS = ["date", "profile", "source", "amount", "notes"]
CURRENCIES = {"INR", "USD"}


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


def load_profiles(root: Path) -> list[Profile]:
    files = sorted((root / "profiles").glob("*.yaml"))
    if not files:
        raise FileNotFoundError(f"no profile YAMLs found in {root / 'profiles'}")
    profiles = []
    for file in files:
        with open(file) as f:
            profiles.append(Profile(key=file.stem, **yaml.safe_load(f)))
    return profiles


def validate_holdings(df: pd.DataFrame, config: Config, profiles: list[Profile]) -> None:
    _check_columns(df, HOLDINGS_COLUMNS, "holdings.csv")
    if df["date"].isna().any():
        raise ValueError("holdings.csv has rows with a missing/invalid date")
    if df["value"].isna().any():
        raise ValueError("holdings.csv has rows with a missing value")
    bad = set(df["category"].dropna()) - set(config.categories)
    if bad:
        raise ValueError(f"holdings.csv uses categories not in config.yaml: {sorted(bad)}")
    bad = set(df["currency"].dropna()) - CURRENCIES
    if bad:
        raise ValueError(f"holdings.csv has unsupported currencies: {sorted(bad)}")
    bad = set(df["profile"].dropna()) - {p.key for p in profiles}
    if bad:
        raise ValueError(f"holdings.csv has unknown profiles: {sorted(bad)}")


def validate_income(df: pd.DataFrame, profiles: list[Profile]) -> None:
    _check_columns(df, INCOME_COLUMNS, "income.csv")
    if df["date"].isna().any():
        raise ValueError("income.csv has rows with a missing/invalid date")
    if df["amount"].isna().any():
        raise ValueError("income.csv has rows with a missing amount")
    bad = set(df["profile"].dropna()) - {p.key for p in profiles}
    if bad:
        raise ValueError(f"income.csv has unknown profiles: {sorted(bad)}")


def load_holdings(root: Path, config: Config, profiles: list[Profile]) -> pd.DataFrame:
    df = pd.read_csv(root / "holdings.csv", parse_dates=["date"])
    validate_holdings(df, config, profiles)
    return df


def load_income(root: Path, profiles: list[Profile]) -> pd.DataFrame:
    df = pd.read_csv(root / "income.csv", parse_dates=["date"])
    validate_income(df, profiles)
    return df


def save_holdings(root: Path, df: pd.DataFrame) -> None:
    _write_csv(df, root / "holdings.csv", sort_by=["date", "profile", "category"])


def save_income(root: Path, df: pd.DataFrame) -> None:
    _write_csv(df, root / "income.csv", sort_by=["date", "profile"])


def _write_csv(df: pd.DataFrame, path: Path, sort_by: list[str]) -> None:
    out = df.sort_values(sort_by).copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False)


def _check_columns(df: pd.DataFrame, expected: list[str], filename: str) -> None:
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise ValueError(f"{filename} is missing columns: {missing}")
