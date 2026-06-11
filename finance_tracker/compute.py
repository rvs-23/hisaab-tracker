"""The financial model, as pure functions over the loaded data.

The app tracks *contributions against a plan*, not market value. For a given
person and year:

  expected[category] = investment_pool × long_term%  +  wants_pool × short_term%
      investment_pool = monthly_investment × 12
      wants_pool      = monthly_wants × 12 × wants_invest_pct

This reproduces the source spreadsheet's "Amount Expected" column exactly.
"actual" comes from contributions.csv; the gap is the shortfall.
"""

from __future__ import annotations

import pandas as pd

from finance_tracker.models import Profile


def split_pct(row) -> dict[str, float]:
    """Derive the needs/wants/investment percentages of salary for display."""
    monthly = row["ending_salary"] / 12
    if not monthly:
        return {"needs": 0.0, "wants": 0.0, "investment": 0.0}
    return {
        "needs": 100 * row["monthly_needs"] / monthly,
        "wants": 100 * row["monthly_wants"] / monthly,
        "investment": 100 * row["monthly_investment"] / monthly,
    }


def projection(profile: Profile, budget: pd.DataFrame) -> pd.DataFrame:
    """Year-by-year salary, yearly investment budget and running cumulative
    invested, from this person's budget rows — reflecting what's in budget.csv."""
    rows = budget[budget["profile"] == profile.key].sort_values("year")
    out = []
    cumulative = 0.0
    for _, r in rows.iterrows():
        invested_this_year = r["monthly_investment"] * 12
        cumulative += invested_this_year
        out.append(
            {
                "year": int(r["year"]),
                "age": int(r["year"]) - profile.birth_year,
                "ending_salary": round(r["ending_salary"]),
                "monthly_needs": round(r["monthly_needs"]),
                "monthly_wants": round(r["monthly_wants"]),
                "monthly_investment": round(r["monthly_investment"]),
                "invested_this_year": round(invested_this_year),
                "cumulative_invested": round(cumulative),
            }
        )
    return pd.DataFrame(out)


def expected_contributions(profile: Profile, budget: pd.DataFrame, year: int) -> dict[str, float]:
    """Planned rupee amount per category for one person/year — the target mix
    applied to that year's investment pool and (wants-derived) short-term pool."""
    row = budget[(budget["profile"] == profile.key) & (budget["year"] == year)]
    if row.empty:
        return {}
    r = row.iloc[0]
    investment_pool = r["monthly_investment"] * 12
    wants_pool = r["monthly_wants"] * 12 * profile.wants_invest_pct / 100

    expected: dict[str, float] = {}
    for cat, pct in profile.target.long_term.items():
        expected[cat] = expected.get(cat, 0.0) + investment_pool * pct / 100
    for cat, pct in profile.target.short_term.items():
        expected[cat] = expected.get(cat, 0.0) + wants_pool * pct / 100
    return expected


def plan_vs_actual(
    profile: Profile, budget: pd.DataFrame, contributions: pd.DataFrame, year: int
) -> pd.DataFrame:
    """Expected vs actual contribution per category for one person/year.
    shortfall = actual − expected (negative = under-invested)."""
    expected = expected_contributions(profile, budget, year)
    actual_rows = contributions[
        (contributions["profile"] == profile.key) & (contributions["year"] == year)
    ]
    actual = actual_rows.groupby("category")["amount"].sum().to_dict()

    categories = list(expected) + [c for c in actual if c not in expected]
    rows = []
    for cat in categories:
        exp = expected.get(cat, 0.0)
        act = actual.get(cat, 0.0)
        rows.append({"category": cat, "expected": exp, "actual": act, "shortfall": act - exp})
    return pd.DataFrame(rows)


def household_plan_vs_actual(
    profiles: list[Profile], budget: pd.DataFrame, contributions: pd.DataFrame, year: int
) -> pd.DataFrame:
    """Plan vs actual summed across everyone for a year."""
    parts = [plan_vs_actual(p, budget, contributions, year) for p in profiles]
    parts = [p for p in parts if not p.empty]
    if not parts:
        return pd.DataFrame(columns=["category", "expected", "actual", "shortfall"])
    return pd.concat(parts).groupby("category", as_index=False)[
        ["expected", "actual", "shortfall"]
    ].sum()


def pct_goal_achieved(pva: pd.DataFrame) -> float:
    """Total actual ÷ total expected, as a percent (the sheet's '%goal achieved')."""
    expected = pva["expected"].sum()
    return 100 * pva["actual"].sum() / expected if expected else 0.0


def available_years(budget: pd.DataFrame, contributions: pd.DataFrame) -> list[int]:
    years = pd.concat([budget["year"], contributions["year"]]).dropna().astype(int)
    return sorted(years.unique().tolist())
