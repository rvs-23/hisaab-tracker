"""Pydantic schemas for the YAML inputs (config.yaml and profiles/*.yaml).

The numeric history (income, contributions, targets) lives in CSVs and is
validated in storage.py — these models cover only the hand-edited YAML.
"""

from __future__ import annotations

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
    """Household-wide settings from config.yaml. Unknown YAML keys are ignored.

    Attributes:
        categories: The shared asset-class vocabulary.
        expected_return_pct: Optional single expected annual return (% p.a.).
            When set, it is THE growth rate everywhere — net worth, corpus,
            catch-up, and the Rent-vs-buy default — replacing the per-category
            ``config.EXPECTED_RETURNS``. Absent, per-category rates apply.
    """

    categories: list[str]
    expected_return_pct: float | None = None
