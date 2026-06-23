"""The financial model, as pure functions over the loaded data.

Budget is *derived from income*, not entered. The philosophy (from the source
workbook) is fixed:

  - In a person's anchor year (their earliest), total income splits 50/30/20
    across needs / wants / investment.
  - Every year after, last year's rupee amounts carry forward and only the
    *increment* in income splits 20/30/50 — so more of each raise is invested.

Then, for contributions tracking, the goal is that year's investment amount
split across instruments by the target allocation:

  expected[category] = investment × target%[category]

"actual" comes from contributions.csv; the gap is the shortfall.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from config import (
    BASE_SPLIT, EXPECTED_RETURNS, INCOME_COMPONENTS, INCREMENT_SPLIT,
    NETWORTH_PROJECTION_YEARS, PROJECTION_YEARS_AHEAD,
)
from models import Profile

BUDGET_COLUMNS = [
    "year", "age", "total_income", "yoy", "job_change", "needs", "wants", "investment",
    "monthly_needs", "monthly_wants", "monthly_investment",
    "invested_this_year", "cumulative_invested", "is_projected",
]


def total_income(row) -> float:
    """Sums a row's income components (salary + bonus + other)."""
    return sum(float(row[c]) for c in INCOME_COMPONENTS)


def annual_income(income: pd.DataFrame) -> pd.DataFrame:
    """Collapses the monthly income rows to one row per (profile, year).

    Income components are summed; ``job_change`` is a per-year flag, so its max
    over the year's rows is kept.
    """
    if income.empty:
        return pd.DataFrame(columns=["profile", "year", *INCOME_COMPONENTS, "job_change"])
    agg = {c: "sum" for c in INCOME_COMPONENTS}
    agg["job_change"] = "max"
    return income.groupby(["profile", "year"], as_index=False).agg(agg)


def budget_series(profile: Profile, income: pd.DataFrame, today: dt.date | None = None) -> pd.DataFrame:
    """Per-year derived budget for one person: total income split into annual +
    monthly needs/wants/investment via the anchor + increment philosophy, with a
    running cumulative invested.

    Beyond the entered years, projects forward to current year + 3: income grows
    by forward_increment_pct and each projected raise splits 20/30/50 like any
    other increment. Projected rows carry is_projected=True."""
    yearly = annual_income(income)
    rows = yearly[yearly["profile"] == profile.key].sort_values("year")
    if rows.empty:
        return pd.DataFrame(columns=BUDGET_COLUMNS)

    out = []
    prev_total = None
    prev = {"needs": 0.0, "wants": 0.0, "investment": 0.0}
    cumulative = 0.0

    def add_year(year: int, total: float, projected: bool, job_change: bool) -> None:
        nonlocal prev_total, prev, cumulative
        if prev_total is None:  # anchor year
            amt = {k: total * BASE_SPLIT[k] / 100 for k in BASE_SPLIT}
        else:
            delta = total - prev_total
            amt = {k: prev[k] + delta * INCREMENT_SPLIT[k] / 100 for k in INCREMENT_SPLIT}
        cumulative += amt["investment"]
        yoy = (total / prev_total - 1) * 100 if prev_total else None
        out.append(
            {
                "year": year,
                "age": year - profile.birth_year,
                "total_income": round(total),
                "yoy": yoy,
                "job_change": job_change,
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
        add_year(int(r["year"]), total_income(r), projected=False,
                 job_change=bool(r.get("job_change", 0)))

    horizon = (today or dt.date.today()).year + PROJECTION_YEARS_AHEAD
    year, total = int(rows["year"].max()), prev_total
    while year < horizon:
        year += 1
        total = total * (1 + profile.forward_increment_pct / 100)
        add_year(year, total, projected=True, job_change=False)

    return pd.DataFrame(out)


# Kept as the name the projection page imports.
projection = budget_series


def split_pct(row) -> dict[str, float]:
    """needs/wants/investment as % of total income, for display."""
    total = row["total_income"]
    if not total:
        return {"needs": 0.0, "wants": 0.0, "investment": 0.0}
    return {k: 100 * row[k] / total for k in ("needs", "wants", "investment")}


def resolve_target(profile: Profile, targets: pd.DataFrame, year: int) -> dict[str, float]:
    """Returns the target allocation in force for a person/year.

    Per-year override rows carry forward: the most recent override year ≤ the
    asked year wins. With no override yet, the profile's default_target applies.
    """
    if not targets.empty:
        mine = targets[(targets["profile"] == profile.key) & (targets["year"] <= year)]
        if not mine.empty:
            rows = mine[mine["year"] == mine["year"].max()]
            return dict(zip(rows["category"], rows["pct"]))
    return dict(profile.default_target)


def expected_contributions(
    profile: Profile, income: pd.DataFrame, targets: pd.DataFrame, year: int
) -> dict[str, float]:
    """Returns the planned rupee amount per category for one person/year.

    The whole goal is that year's investment amount, split across instruments by
    the target allocation: ``expected[cat] = investment × target%[cat]``.
    """
    bs = budget_series(profile, income)
    row = bs[bs["year"] == year]
    if row.empty:
        return {}
    investment = row.iloc[0]["investment"]
    target = resolve_target(profile, targets, year)
    return {cat: investment * pct / 100 for cat, pct in target.items()}


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


def emergency_fund_held(profile: Profile, goals: pd.DataFrame) -> float:
    """Returns the latest emergency-fund goal for a person (held cash, no growth)."""
    g = goals[goals["profile"] == profile.key]
    return float(g.sort_values("year").iloc[-1]["emergency_fund_goal"]) if not g.empty else 0.0


def net_worth_to_date(profile: Profile, contributions: pd.DataFrame, goals: pd.DataFrame,
                      today_year: int) -> tuple[int, int]:
    """Returns (actual, potential) net worth as of ``today_year``.

    ``actual`` is contributions put in (cost basis) plus the emergency fund.
    ``potential`` compounds each contribution at its category's expected return
    and adds the emergency fund. The gap between them is the expected growth.
    """
    c = contributions[contributions["profile"] == profile.key]
    invested = float(c["amount"].sum())
    grown = sum(
        float(r.amount) * (1 + EXPECTED_RETURNS.get(r.category, 0) / 100) ** max(0, today_year - int(r.year))
        for r in c.itertuples()
    )
    ef = emergency_fund_held(profile, goals)
    return round(invested + ef), round(grown + ef)


def net_worth_series(profile: Profile, income: pd.DataFrame, contributions: pd.DataFrame,
                     targets: pd.DataFrame, goals: pd.DataFrame, today_year: int,
                     ahead: int = NETWORTH_PROJECTION_YEARS) -> pd.DataFrame:
    """Net worth year by year, actual past plus a projected future.

    Past years use actual contributions. Future years assume the plan continues:
    this year's investment grown at ``forward_increment_pct``, allocated by the
    current target. Returns a frame with ``year``, ``cost_basis`` (no growth),
    ``potential`` (compounded), and ``is_projected``.
    """
    c = contributions[contributions["profile"] == profile.key]
    years = [int(y) for y in c["year"].unique()]
    first = min(years) if years else today_year

    streams: dict[int, dict[str, float]] = {}
    for y in range(first, today_year + 1):
        streams[y] = c[c["year"] == y].groupby("category")["amount"].sum().to_dict()

    bs = budget_series(profile, income)
    cur = bs[bs["year"] == today_year]
    cur_invest = float(cur.iloc[0]["investment"]) if not cur.empty else 0.0
    target = resolve_target(profile, targets, today_year)
    for i in range(1, ahead + 1):
        invest_y = cur_invest * (1 + profile.forward_increment_pct / 100) ** i
        streams[today_year + i] = {cat: invest_y * pct / 100 for cat, pct in target.items()}

    ef = emergency_fund_held(profile, goals)
    rows = []
    for horizon in range(first, today_year + ahead + 1):
        potential = basis = ef
        for y in range(first, horizon + 1):
            for cat, amt in streams.get(y, {}).items():
                potential += amt * (1 + EXPECTED_RETURNS.get(cat, 0) / 100) ** (horizon - y)
                basis += amt
        rows.append({"year": horizon, "cost_basis": round(basis), "potential": round(potential),
                     "is_projected": horizon > today_year})
    return pd.DataFrame(rows)
