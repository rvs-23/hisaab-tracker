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


def monthly_budget(
    ending_salary: float, needs_pct: float, wants_pct: float, investment_pct: float
) -> dict[str, float]:
    """Split a year's gross salary into monthly needs/wants/investment amounts."""
    monthly = ending_salary / 12
    return {
        "needs": monthly * needs_pct / 100,
        "wants": monthly * wants_pct / 100,
        "investment": monthly * investment_pct / 100,
    }


def projection(profile: Profile, budget: pd.DataFrame) -> pd.DataFrame:
    """Year-by-year salary, yearly investment budget and running cumulative
    invested, from this person's budget rows — reflecting what's in budget.csv."""
    rows = budget[budget["profile"] == profile.key].sort_values("year")
    out = []
    cumulative = 0.0
    for _, r in rows.iterrows():
        mb = monthly_budget(r["ending_salary"], r["needs_pct"], r["wants_pct"], r["investment_pct"])
        invested_this_year = mb["investment"] * 12
        cumulative += invested_this_year
        out.append(
            {
                "year": int(r["year"]),
                "age": int(r["year"]) - profile.birth_year,
                "ending_salary": round(r["ending_salary"]),
                "monthly_needs": round(mb["needs"]),
                "monthly_wants": round(mb["wants"]),
                "monthly_investment": round(mb["investment"]),
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
    mb = monthly_budget(r["ending_salary"], r["needs_pct"], r["wants_pct"], r["investment_pct"])
    investment_pool = mb["investment"] * 12
    wants_pool = mb["wants"] * 12 * profile.wants_invest_pct / 100

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
