"""The spreadsheet-model computations, as pure functions over the loaded data.

1. budget_split      — monthly salary -> needs/wants/investment amounts
2. projection        — multi-year salary growth + cumulative invested
3. allocation        — current holdings aggregated by category (INR, %)
4. plan_vs_actual    — target mix vs actual allocation, surplus/shortfall
plus net-worth history derived from the dated holdings rows.
"""

from __future__ import annotations

import pandas as pd

from finance_tracker.models import Config, Profile


def budget_split(profile: Profile) -> dict[str, float]:
    s = profile.split
    salary = profile.monthly_salary
    return {
        "needs": salary * s.needs / 100,
        "wants": salary * s.wants / 100,
        "investment": salary * s.investment / 100,
    }


def projection(profile: Profile) -> pd.DataFrame:
    """Year-by-year: salary grows by increment_pct annually, the monthly
    investment contribution accumulates into a running cumulative invested.
    No return assumptions — contributions only, as in the spreadsheet."""
    rows = []
    salary = profile.monthly_salary
    cumulative = 0.0
    for i in range(profile.projection_years):
        year = profile.projection_start_year + i
        monthly_investment = salary * profile.split.investment / 100
        cumulative += monthly_investment * 12
        rows.append(
            {
                "year": year,
                "age": year - profile.birth_year,
                "monthly_salary": round(salary),
                "monthly_investment": round(monthly_investment),
                "invested_this_year": round(monthly_investment * 12),
                "cumulative_invested": round(cumulative),
            }
        )
        salary *= 1 + profile.salary_increment_pct / 100
    return pd.DataFrame(rows)


def to_inr(holdings: pd.DataFrame, config: Config) -> pd.DataFrame:
    """Add a value_inr column; USD rows convert at the user-stated rate."""
    df = holdings.copy()
    rates = {"INR": 1.0, "USD": config.usd_inr_rate}
    df["value_inr"] = df["value"] * df["currency"].map(rates)
    return df


def current_holdings(holdings: pd.DataFrame) -> pd.DataFrame:
    """The latest snapshot per profile. Profiles may update on different
    dates, so 'current' is each profile's rows at its own max date."""
    if holdings.empty:
        return holdings
    latest = holdings.groupby("profile")["date"].transform("max")
    return holdings[holdings["date"] == latest]


def allocation(
    holdings: pd.DataFrame, config: Config, profile_key: str | None = None
) -> pd.DataFrame:
    """Current value and % of portfolio by category, for one profile or
    (profile_key=None) the combined household."""
    df = to_inr(current_holdings(holdings), config)
    if profile_key is not None:
        df = df[df["profile"] == profile_key]
    by_cat = df.groupby("category", as_index=False)["value_inr"].sum()
    total = by_cat["value_inr"].sum()
    by_cat["pct"] = 100 * by_cat["value_inr"] / total if total else 0.0
    return by_cat.sort_values("value_inr", ascending=False).reset_index(drop=True)


def plan_vs_actual(
    holdings: pd.DataFrame, config: Config, profile_key: str | None = None
) -> pd.DataFrame:
    """Target % (config.target_mix) vs actual allocation. diff_inr > 0 means
    surplus in that category, < 0 means shortfall."""
    alloc = allocation(holdings, config, profile_key)
    total = alloc["value_inr"].sum()
    actual = dict(zip(alloc["category"], alloc["value_inr"]))
    categories = [c for c in config.categories if c in config.target_mix or c in actual]
    rows = []
    for cat in categories:
        target_pct = config.target_mix.get(cat, 0.0)
        actual_inr = actual.get(cat, 0.0)
        target_inr = total * target_pct / 100
        rows.append(
            {
                "category": cat,
                "target_pct": target_pct,
                "actual_pct": 100 * actual_inr / total if total else 0.0,
                "target_inr": target_inr,
                "actual_inr": actual_inr,
                "diff_inr": actual_inr - target_inr,
            }
        )
    return pd.DataFrame(rows)


def networth_history(
    holdings: pd.DataFrame, config: Config, profiles: list[Profile]
) -> pd.DataFrame:
    """Net worth per snapshot date, one column per person plus Household.
    Between a profile's snapshots its last known value carries forward, so
    staggered update dates still produce a sensible household line."""
    df = to_inr(holdings, config)
    pivot = (
        df.groupby(["date", "profile"])["value_inr"].sum().unstack("profile").sort_index().ffill()
    )
    names = {p.key: p.name for p in profiles}
    pivot = pivot.rename(columns=names)
    pivot["Household"] = pivot.sum(axis=1)
    return pivot
