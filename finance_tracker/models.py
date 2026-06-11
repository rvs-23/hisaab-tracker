"""Pydantic schemas for the YAML inputs (config.yaml and profiles/*.yaml).

The numeric history (budget rows, contributions, goals) lives in CSVs and is
validated in storage.py — these models cover only the hand-edited YAML.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, model_validator


def _check_sums_to_100(mix: dict[str, float], where: str) -> None:
    total = sum(mix.values())
    if abs(total - 100) > 0.01:
        raise ValueError(f"{where} must sum to 100, got {total}")


class Target(BaseModel):
    """One person's target allocation, constant across years. Two tiers because
    wants-money and investment-money are deployed to different mixes:
      short_term — where the invested slice of *wants* money goes
      long_term  — where *investment* money goes
    Each tier is a {category: percent} map summing to 100."""

    short_term: dict[str, float]
    long_term: dict[str, float]

    @model_validator(mode="after")
    def _tiers_sum_to_100(self) -> "Target":
        _check_sums_to_100(self.short_term, "target.short_term")
        _check_sums_to_100(self.long_term, "target.long_term")
        return self


class Profile(BaseModel):
    """One person. Loaded from profiles/<key>.yaml; `key` is the filename stem
    and is the value used in the `profile` column of every CSV.

    `default_target` is the fallback allocation; per-year overrides live in
    targets.csv and win for the years they cover."""

    key: str
    name: str
    birth_year: int
    forward_increment_pct: float  # assumed annual raise for projected future years
    wants_invest_pct: float       # % of wants money that gets invested (short-term tier)
    default_target: Target


class Config(BaseModel):
    """Household-wide settings from config.yaml. Targets are per-profile now;
    config only holds the shared category vocabulary and the FX rate."""

    usd_inr_rate: float
    usd_inr_as_of: dt.date
    categories: list[str]
