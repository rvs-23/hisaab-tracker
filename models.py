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
    def _target_is_a_valid_allocation(self) -> "Profile":
        """An allocation must sum to 100 *and* hold no negative weight.

        Summing to 100 alone lets a typo through — -20% here and 120% there
        balances arithmetically but is not an allocation anyone can hold, and
        it would quietly skew every expected-return calculation.
        """
        if not self.default_target:
            raise ValueError("default_target must list at least one category")
        negative = sorted(c for c, pct in self.default_target.items() if pct < 0)
        if negative:
            raise ValueError(f"default_target has negative weights: {', '.join(negative)}")
        total = sum(self.default_target.values())
        if abs(total - 100) > 0.01:
            raise ValueError(f"default_target must sum to 100, got {total}")
        if self.birth_year < 1900 or self.birth_year > 2100:
            raise ValueError(f"birth_year looks wrong: {self.birth_year}")
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

    @model_validator(mode="after")
    def _sane_household_settings(self) -> "Config":
        """Guards the two ways this file can silently break the whole model."""
        if not self.categories:
            raise ValueError("categories must not be empty")
        duplicates = sorted({c for c in self.categories if self.categories.count(c) > 1})
        if duplicates:
            raise ValueError(f"categories has duplicates: {', '.join(duplicates)}")
        rate = self.expected_return_pct
        if rate is not None and not 0 <= rate <= 30:
            raise ValueError(f"expected_return_pct must be 0-30, got {rate}")
        return self
