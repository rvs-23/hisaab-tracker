"""Pydantic schemas for the YAML inputs (config.yaml and profiles/*.yaml)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, model_validator


class Split(BaseModel):
    """Monthly salary split, in percent. Must sum to 100."""

    needs: float
    wants: float
    investment: float

    @model_validator(mode="after")
    def _sums_to_100(self) -> "Split":
        total = self.needs + self.wants + self.investment
        if abs(total - 100) > 0.01:
            raise ValueError(f"split percentages must sum to 100, got {total}")
        return self


class Profile(BaseModel):
    """One person. Loaded from profiles/<key>.yaml; `key` is the filename stem
    and is the value used in the `profile` column of holdings.csv / income.csv."""

    key: str
    name: str
    birth_year: int
    monthly_salary: float
    salary_increment_pct: float
    split: Split
    projection_start_year: int
    projection_years: int


class Config(BaseModel):
    """Household-wide settings from config.yaml."""

    usd_inr_rate: float
    usd_inr_as_of: dt.date
    categories: list[str]
    target_mix: dict[str, float]

    @model_validator(mode="after")
    def _check_target_mix(self) -> "Config":
        unknown = set(self.target_mix) - set(self.categories)
        if unknown:
            raise ValueError(
                f"target_mix uses categories missing from `categories`: {sorted(unknown)}"
            )
        total = sum(self.target_mix.values())
        if abs(total - 100) > 0.01:
            raise ValueError(f"target_mix must sum to 100, got {total}")
        return self
