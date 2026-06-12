"""The financial model, as pure functions over the loaded data.

Budget is *derived from income*, not entered. The philosophy (from the source
workbook) is fixed:

  - In a person's anchor year (their earliest), total income splits 50/30/20
    across needs / wants / investment.
  - Every year after, last year's rupee amounts carry forward and only the
    *increment* in income splits 20/30/50 — so more of each raise is invested.

Then, for contributions tracking:

  expected[category] = investment_pool × long_term%  +  wants_pool × short_term%
      investment_pool = that year's investment amount
      wants_pool      = that year's wants amount × wants_invest_pct

"actual" comes from contributions.csv; the gap is the shortfall.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from finance_tracker.models import Profile

BASE_SPLIT = {"needs": 50, "wants": 30, "investment": 20}        # anchor-year split
INCREMENT_SPLIT = {"needs": 20, "wants": 30, "investment": 50}   # split of each raise
PROJECTION_YEARS_AHEAD = 3  # budget extends to current year + 3

BUDGET_COLUMNS = [
    "year", "age", "total_income", "needs", "wants", "investment",
    "monthly_needs", "monthly_wants", "monthly_investment",
    "invested_this_year", "cumulative_invested", "is_projected",
]


def total_income(row) -> float:
    return float(row["salary"]) + float(row["bonus"]) + float(row["other"])


def budget_series(profile: Profile, income: pd.DataFrame, today: dt.date | None = None) -> pd.DataFrame:
    """Per-year derived budget for one person: total income split into annual +
    monthly needs/wants/investment via the anchor + increment philosophy, with a
    running cumulative invested.

    Beyond the entered years, projects forward to current year + 3: income grows
    by forward_increment_pct and each projected raise splits 20/30/50 like any
    other increment. Projected rows carry is_projected=True."""
    rows = income[income["profile"] == profile.key].sort_values("year")
    if rows.empty:
        return pd.DataFrame(columns=BUDGET_COLUMNS)

    out = []
    prev_total = None
    prev = {"needs": 0.0, "wants": 0.0, "investment": 0.0}
    cumulative = 0.0

    def add_year(year: int, total: float, projected: bool) -> None:
        nonlocal prev_total, prev, cumulative
        if prev_total is None:  # anchor year
            amt = {k: total * BASE_SPLIT[k] / 100 for k in BASE_SPLIT}
        else:
            delta = total - prev_total
            amt = {k: prev[k] + delta * INCREMENT_SPLIT[k] / 100 for k in INCREMENT_SPLIT}
        cumulative += amt["investment"]
        out.append(
            {
                "year": year,
                "age": year - profile.birth_year,
                "total_income": round(total),
                "needs": round(amt["needs"]),
                "wants": round(amt["wants"]),
                "investment": round(amt["investment"]),
                "monthly_needs": round(amt["needs"] / 12),
                "monthly_wants": round(amt["wants"] / 12),
                "monthly_investment": round(amt["investment"] / 12),
                "invested_this_year": round(amt["investment"]),
                "cumulative_invested": round(cumulative),
                "is_projected": projected,
            }
        )
        prev_total, prev = total, amt

    for _, r in rows.iterrows():
        add_year(int(r["year"]), total_income(r), projected=False)

    horizon = (today or dt.date.today()).year + PROJECTION_YEARS_AHEAD
    year, total = int(rows["year"].max()), prev_total
    while year < horizon:
        year += 1
        total = total * (1 + profile.forward_increment_pct / 100)
        add_year(year, total, projected=True)

    return pd.DataFrame(out)


# Kept as the name the projection page imports.
projection = budget_series


def split_pct(row) -> dict[str, float]:
    """needs/wants/investment as % of total income, for display."""
    total = row["total_income"]
    if not total:
        return {"needs": 0.0, "wants": 0.0, "investment": 0.0}
    return {k: 100 * row[k] / total for k in ("needs", "wants", "investment")}


def resolve_target(profile: Profile, targets: pd.DataFrame, year: int) -> dict[str, dict[str, float]]:
    """The allocation in force for a person/year. Target rows carry forward: the
    most recent override year ≤ the asked year wins; with no override yet, the
    profile's default_target applies. A tier missing from the override falls
    back to the default for that tier."""
    default = {
        "short_term": dict(profile.default_target.short_term),
        "long_term": dict(profile.default_target.long_term),
    }
    if targets.empty:
        return default
    mine = targets[(targets["profile"] == profile.key) & (targets["year"] <= year)]
    if mine.empty:
        return default
    rows = mine[mine["year"] == mine["year"].max()]
    out: dict[str, dict[str, float]] = {"short_term": {}, "long_term": {}}
    for _, r in rows.iterrows():
        out[r["tier"]][r["category"]] = r["pct"]
    for tier in out:
        if not out[tier]:
            out[tier] = default[tier]
    return out


def expected_contributions(
    profile: Profile, income: pd.DataFrame, targets: pd.DataFrame, year: int
) -> dict[str, float]:
    """Planned rupee amount per category for one person/year — the target mix
    applied to that year's investment pool and (wants-derived) short-term pool."""
    bs = budget_series(profile, income)
    row = bs[bs["year"] == year]
    if row.empty:
        return {}
    r = row.iloc[0]
    investment_pool = r["investment"]
    wants_pool = r["wants"] * profile.wants_invest_pct / 100
    target = resolve_target(profile, targets, year)

    expected: dict[str, float] = {}
    for cat, pct in target["long_term"].items():
        expected[cat] = expected.get(cat, 0.0) + investment_pool * pct / 100
    for cat, pct in target["short_term"].items():
        expected[cat] = expected.get(cat, 0.0) + wants_pool * pct / 100
    return expected


def plan_vs_actual(
    profile: Profile, income: pd.DataFrame, targets: pd.DataFrame,
    contributions: pd.DataFrame, year: int,
) -> pd.DataFrame:
    """Expected vs actual contribution per category for one person/year.
    shortfall = actual − expected (negative = under-invested)."""
    expected = expected_contributions(profile, income, targets, year)
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
    profiles: list[Profile], income: pd.DataFrame, targets: pd.DataFrame,
    contributions: pd.DataFrame, year: int,
) -> pd.DataFrame:
    """Plan vs actual summed across the given people for a year."""
    parts = [plan_vs_actual(p, income, targets, contributions, year) for p in profiles]
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


def available_years(income: pd.DataFrame, contributions: pd.DataFrame) -> list[int]:
    years = pd.concat([income["year"], contributions["year"]]).dropna().astype(int)
    return sorted(years.unique().tolist())
