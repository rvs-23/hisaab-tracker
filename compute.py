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
    BASE_SPLIT, BASELINE_YEAR, EMERGENCY_FUND_MONTHS, EXPECTED_RETURNS,
    INCOME_COMPONENTS, INCREMENT_SPLIT, NETWORTH_PROJECTION_YEARS,
    PROJECTION_YEARS_AHEAD,
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
    other increment. Projected rows carry is_projected=True.

    Zero-income years get no budget row: the anchor is the first *earning* year
    (an all-zero 2022 baseline must not steal the 50/30/20 anchor split from the
    real first year), and a mid-series zero year is skipped like a missing one.
    A year earning *less* than the last scales the previous buckets down
    proportionally — the split still sums to the new total and never goes
    negative."""
    yearly = annual_income(income)
    rows = yearly[yearly["profile"] == profile.key].sort_values("year")

    out = []
    prev_total = None
    prev = {"needs": 0.0, "wants": 0.0, "investment": 0.0}
    cumulative = 0.0

    def add_year(year: int, total: float, projected: bool, job_change: bool) -> None:
        nonlocal prev_total, prev, cumulative
        if prev_total is None:  # anchor year
            amt = {k: total * BASE_SPLIT[k] / 100 for k in BASE_SPLIT}
        elif total < prev_total:  # income drop: shrink all buckets proportionally
            amt = {k: prev[k] * total / prev_total for k in prev}
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
        total = total_income(r)
        if total <= 0:
            continue  # no earnings, no budget row (see docstring)
        add_year(int(r["year"]), total, projected=False,
                 job_change=bool(r.get("job_change", 0)))

    if prev_total is None:  # no earning years at all
        return pd.DataFrame(columns=BUDGET_COLUMNS)

    horizon = (today or dt.date.today()).year + PROJECTION_YEARS_AHEAD
    year, total = int(rows["year"].max()), prev_total
    while year < horizon:
        year += 1
        total = total * (1 + profile.forward_increment_pct / 100)
        add_year(year, total, projected=True, job_change=False)

    return pd.DataFrame(out)


def opening_corpus(adjustments: pd.DataFrame, profile_key: str) -> float:
    """Returns a person's opening corpus — money invested before tracking
    began — or ``0.0`` if none is recorded (see ``storage.load_adjustments``)."""
    if adjustments.empty:
        return 0.0
    rows = adjustments[
        (adjustments["profile"] == profile_key) & (adjustments["field"] == "opening_corpus")
    ]
    return float(rows.iloc[0]["value"]) if not rows.empty else 0.0


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


def available_years(income: pd.DataFrame, contributions: pd.DataFrame,
                    profile: str | None = None) -> list[int]:
    """Sorted years that have income or contribution rows.

    Pass ``profile`` (a profile key) to scope to one person — after per-person
    routing, callers want only the active person's years, not everyone's.
    """
    inc, con = income, contributions
    if profile is not None:
        inc = inc[inc["profile"] == profile]
        con = con[con["profile"] == profile]
    years = pd.concat([inc["year"], con["year"]]).dropna().astype(int)
    return sorted(years.unique().tolist())


def selectable_years(income: pd.DataFrame, contributions: pd.DataFrame,
                     profile: str | None = None, today: dt.date | None = None) -> list[int]:
    """The locked year range every page selector offers: a contiguous span from
    ``BASELINE_YEAR`` (2022, the zero floor) up to the current year — or the
    latest year that has data, if somehow later. Profile-scoped when a key is
    given. Always non-empty, so a selector never collapses."""
    cur = (today or dt.date.today()).year
    top = max([cur, *available_years(income, contributions, profile)])
    return list(range(BASELINE_YEAR, top + 1))


def emergency_fund_target(profile: Profile, income: pd.DataFrame, year: int | None = None) -> float:
    """The emergency-fund buffer: ``EMERGENCY_FUND_MONTHS`` months of the needs
    bucket (6 × monthly needs). Derived from income like the rest of the budget,
    never entered. Defaults to the latest non-projected year."""
    bs = budget_series(profile, income)
    if bs.empty:
        return 0.0
    pool = bs[~bs["is_projected"]]
    if pool.empty:
        pool = bs
    row = pool[pool["year"] == year] if year is not None else pool.iloc[[-1]]
    if row.empty:
        row = pool.iloc[[-1]]
    return float(row.iloc[0]["monthly_needs"]) * EMERGENCY_FUND_MONTHS


def corpus_vintage_year(income: pd.DataFrame, contributions: pd.DataFrame,
                        profile_key: str) -> int | None:
    """The assumed vintage of a person's opening corpus (pre-tracking
    investments): the start of their first tracked year, i.e. the earliest
    year with any income or contribution rows. ``None`` if they have no data
    at all to anchor it to."""
    years = available_years(income, contributions, profile_key)
    return years[0] if years else None


def _corpus_growth_rate(profile: Profile, targets: pd.DataFrame, vintage: int) -> float:
    """The opening corpus's assumed annual return: the target allocation in
    force at its vintage year, weighted by each category's expected return."""
    target = resolve_target(profile, targets, vintage)
    return sum(pct / 100 * EXPECTED_RETURNS.get(cat, 0) for cat, pct in target.items())


def net_worth_to_date(profile: Profile, income: pd.DataFrame, contributions: pd.DataFrame,
                      targets: pd.DataFrame, today_year: int,
                      opening: float = 0.0) -> tuple[int, int]:
    """Returns (actual, potential) net worth as of ``today_year``.

    ``actual`` is contributions put in (cost basis) plus the emergency fund.
    ``potential`` compounds each contribution at its category's expected return
    and adds the emergency fund. The gap between them is the expected growth.

    ``opening`` is a person's opening corpus — money invested before tracking
    began (see ``storage.load_adjustments``). It counts at face value in
    ``actual`` and compounded from its vintage year (their first tracked year,
    see ``corpus_vintage_year``) to ``today_year`` in ``potential``, at the
    allocation-weighted expected return in force that year. Contributes
    nothing to either if ``today_year`` is before the vintage, or if the
    person has no data to anchor a vintage to.
    """
    c = contributions[contributions["profile"] == profile.key]
    invested = float(c["amount"].sum())
    grown = sum(
        float(r.amount) * (1 + EXPECTED_RETURNS.get(r.category, 0) / 100) ** max(0, today_year - int(r.year))
        for r in c.itertuples()
    )
    ef = emergency_fund_target(profile, income, today_year)
    vintage = corpus_vintage_year(income, contributions, profile.key)
    corpus_actual = corpus_potential = 0.0
    if opening and vintage is not None and today_year >= vintage:
        rate = _corpus_growth_rate(profile, targets, vintage)
        corpus_actual = opening
        corpus_potential = opening * (1 + rate / 100) ** (today_year - vintage)
    return round(invested + ef + corpus_actual), round(grown + ef + corpus_potential)


def elapsed_year_fraction(today: dt.date | None = None) -> float:
    """Returns how far ``today`` is into its calendar year.

    Args:
        today: The date to measure; defaults to the real today. Pass an
            explicit date for deterministic tests.

    Returns:
        Day-of-year ÷ days-in-year (365 or 366), so mid-year is ≈ 0.5 and
        December 31 is ≈ 1.0.
    """
    today = today or dt.date.today()
    days_in_year = (dt.date(today.year + 1, 1, 1) - dt.date(today.year, 1, 1)).days
    return today.timetuple().tm_yday / days_in_year


def catch_up_amount(profile: Profile, income: pd.DataFrame, targets: pd.DataFrame,
                    contributions: pd.DataFrame, today_year: int,
                    today: dt.date | None = None) -> float:
    """Lump sum to invest today to pull level with the planned trajectory.

    For every planned year up to today, the per-category shortfall (planned −
    actual) is grown to today at that category's expected return; surpluses in
    other years/categories net against it. The current year (``today_year``)
    counts only its elapsed fraction of the plan (see ``elapsed_year_fraction``)
    — you can't be behind on a raise the calendar hasn't gotten to yet; every
    earlier year counts in full. The result is how much, invested *today*
    (already at today's value), would make the portfolio worth what it would
    have been worth had every year's plan been met. Never below zero, and
    investing more than this (overshooting the goal) is fine.
    """
    c = contributions[contributions["profile"] == profile.key]
    fraction = elapsed_year_fraction(today)
    planned_fv = actual_fv = 0.0
    for y in available_years(income, contributions, profile.key):
        if y > today_year:
            continue
        exp = expected_contributions(profile, income, targets, y)
        if y == today_year:
            exp = {cat: amt * fraction for cat, amt in exp.items()}
        act = c[c["year"] == y].groupby("category")["amount"].sum().to_dict()
        for cat in set(exp) | set(act):
            grow = (1 + EXPECTED_RETURNS.get(cat, 0) / 100) ** (today_year - y)
            planned_fv += exp.get(cat, 0.0) * grow
            actual_fv += act.get(cat, 0.0) * grow
    return max(0.0, planned_fv - actual_fv)


def net_worth_series(profile: Profile, income: pd.DataFrame, contributions: pd.DataFrame,
                     targets: pd.DataFrame, today_year: int,
                     ahead: int = NETWORTH_PROJECTION_YEARS,
                     opening: float = 0.0) -> pd.DataFrame:
    """Net worth year by year, actual past plus a projected future.

    Past years use actual contributions. Future years assume the plan continues:
    this year's investment grown at ``forward_increment_pct``, allocated by the
    current target. Returns a frame with ``year``, ``cost_basis`` (no growth),
    ``potential`` (compounded), and ``is_projected``.

    ``opening`` (see ``net_worth_to_date``) is added flat to ``cost_basis`` and
    compounded to ``potential`` for every horizon year at or after its vintage
    (the person's first tracked year); horizon years before that get nothing.
    """
    c = contributions[contributions["profile"] == profile.key]
    years = [int(y) for y in c["year"].unique()]
    vintage = corpus_vintage_year(income, contributions, profile.key)
    include_corpus = bool(opening) and vintage is not None
    candidates = years + ([vintage] if include_corpus else [])
    first = min(candidates) if candidates else today_year
    corpus_rate = _corpus_growth_rate(profile, targets, vintage) if include_corpus else 0.0

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

    ef = emergency_fund_target(profile, income, today_year)
    rows = []
    for horizon in range(first, today_year + ahead + 1):
        potential = basis = ef
        for y in range(first, horizon + 1):
            for cat, amt in streams.get(y, {}).items():
                potential += amt * (1 + EXPECTED_RETURNS.get(cat, 0) / 100) ** (horizon - y)
                basis += amt
        if include_corpus and horizon >= vintage:
            basis += opening
            potential += opening * (1 + corpus_rate / 100) ** (horizon - vintage)
        rows.append({"year": horizon, "cost_basis": round(basis), "potential": round(potential),
                     "is_projected": horizon > today_year})
    return pd.DataFrame(rows)
