"""Pydantic schemas for the YAML inputs (config.yaml and profiles/*.yaml).

The numeric history (income, contributions, targets) lives in CSVs and is
validated in storage.py — these models cover only the hand-edited YAML.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, model_validator


class Profile(BaseModel):
    """One person, loaded from profiles/<key>.yaml.

    Attributes:
        key: Filename stem; the value used in the `profile` column of every CSV.
        name: Display name.
        birth_year: Used to show age in the budget projection.
        forward_increment_pct: Assumed annual income growth for projected years.
        default_target: Fallback allocation as a {category: percent} map summing
            to 100. Per-year overrides live in targets.csv and win for the years
            they cover.
    """

    key: str
    name: str
    birth_year: int
    forward_increment_pct: float
    default_target: dict[str, float]

    @model_validator(mode="after")
    def _target_sums_to_100(self) -> "Profile":
        total = sum(self.default_target.values())
        if abs(total - 100) > 0.01:
            raise ValueError(f"default_target must sum to 100, got {total}")
        return self


class Config(BaseModel):
    """Household-wide settings from config.yaml. Targets are per-profile now;
    config only holds the shared category vocabulary and the FX rate."""

    usd_inr_rate: float
    usd_inr_as_of: dt.date
    categories: list[str]
