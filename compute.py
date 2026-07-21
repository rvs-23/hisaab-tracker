"""The financial model, as pure functions over the loaded data.

Budget is *derived from income*, not entered. The philosophy is fixed; the
split percentages are per person (config.PROFILE_BASE_SPLITS / _INCREMENT_SPLITS):

  - In a person's anchor year (their first earning year), total income splits
    across needs / wants / investment per their base split.
  - Every year after, last year's rupee amounts carry forward and only the
    *increment* in income splits per their increment split — so more of each
    raise is invested.

Then, for contributions tracking, the goal is that year's investment amount
split across instruments by the target allocation:

  expected[category] = investment × target%[category]

"actual" comes from contributions.csv; the gap is the shortfall.
"""

from __future__ import annotations

import datetime as dt
from typing import Callable

import pandas as pd

from config import (
    BASELINE_YEAR, CATEGORY_LABELS, DEFAULT_BASE_SPLIT, DEFAULT_INCREMENT_SPLIT,
    EMERGENCY_FUND_MONTHS, EXPECTED_RETURNS, INCOME_COMPONENTS,
    NETWORTH_PROJECTION_YEARS, PROFILE_BASE_SPLITS, PROFILE_INCREMENT_SPLITS,
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
    by forward_increment_pct and each projected raise splits per the person's
    increment split like any
    other increment. Projected rows carry is_projected=True.

    Zero-income years get no budget row: the anchor is the first *earning* year
    (an all-zero 2022 baseline must not steal the anchor split from the
    real first year), and a mid-series zero year is skipped like a missing one.
    A year earning *less* than the last scales the previous buckets down
    proportionally — the split still sums to the new total and never goes
    negative."""
    yearly = annual_income(income)
    rows = yearly[yearly["profile"] == profile.key].sort_values("year")
    base_split = PROFILE_BASE_SPLITS.get(profile.key, DEFAULT_BASE_SPLIT)
    increment_split = PROFILE_INCREMENT_SPLITS.get(profile.key, DEFAULT_INCREMENT_SPLIT)

    out = []
    prev_total = None
    prev = {"needs": 0.0, "wants": 0.0, "investment": 0.0}
    cumulative = 0.0

    def add_year(year: int, total: float, projected: bool, job_change: bool) -> None:
        nonlocal prev_total, prev, cumulative
        if prev_total is None:  # anchor year
            amt = {k: total * base_split[k] / 100 for k in base_split}
        elif total < prev_total:  # income drop: shrink all buckets proportionally
            amt = {k: prev[k] * total / prev_total for k in prev}
        else:
            delta = total - prev_total
            amt = {k: prev[k] + delta * increment_split[k] / 100 for k in increment_split}
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


def category_return(category: str, flat_return: float | None = None) -> float:
    """The expected annual return (% p.a.) for a category.

    Args:
        category: Asset-class key.
        flat_return: Optional single household rate (config.yaml
            ``expected_return_pct``). When given it wins for every category —
            "we only use one" — else the per-category ``EXPECTED_RETURNS``.
    """
    if flat_return is not None:
        return flat_return
    return EXPECTED_RETURNS.get(category, 0)


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
    """The emergency-fund *target*: ``EMERGENCY_FUND_MONTHS`` months of the
    needs bucket (essential spending only — wants pause in an emergency).
    Derived from income like the rest of the budget; the *actual* fund held is
    a hand-entered adjustment (see ``emergency_fund_actual``). Defaults to the
    latest non-projected year."""
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


def expected_return_for_target(target: dict[str, float], flat_return: float | None = None) -> float:
    """The allocation-weighted expected annual return for a target mix (%).

    E.g. 45% mfs @ 11.5% + 25% gold @ 7.5% + ... Used for the opening
    corpus's assumed growth (``_corpus_growth_rate``) and exposed publicly so
    other callers (e.g. the rent-vs-buy calculator's default invest return)
    can reuse the same weighting instead of hard-coding a number.
    """
    if flat_return is not None:
        return flat_return
    return sum(pct / 100 * category_return(cat) for cat, pct in target.items())


def _corpus_growth_rate(profile: Profile, targets: pd.DataFrame, vintage: int,
                        flat_return: float | None = None) -> float:
    """The opening corpus's assumed annual return: the target allocation in
    force at its vintage year, weighted by each category's expected return."""
    return expected_return_for_target(resolve_target(profile, targets, vintage), flat_return)


def emergency_fund_actual(adjustments: pd.DataFrame, profile_key: str) -> float:
    """Returns the emergency fund a person actually holds (hand-entered), or
    ``0.0`` if none is recorded (see ``storage.load_adjustments``)."""
    if adjustments.empty:
        return 0.0
    rows = adjustments[
        (adjustments["profile"] == profile_key) & (adjustments["field"] == "emergency_fund")
    ]
    return float(rows.iloc[0]["value"]) if not rows.empty else 0.0


def net_worth_to_date(profile: Profile, income: pd.DataFrame, contributions: pd.DataFrame,
                      targets: pd.DataFrame, today_year: int,
                      opening: float = 0.0,
                      emergency_fund: float | None = None,
                      flat_return: float | None = None) -> tuple[int, int]:
    """Returns (actual, potential) net worth as of ``today_year``.

    ``actual`` is contributions put in (cost basis) plus the emergency fund.
    ``potential`` compounds each contribution at its category's expected return
    and adds the emergency fund. The gap between them is the expected growth.

    ``emergency_fund`` is the fund actually held (hand-entered, no growth);
    ``None`` falls back to the derived target — the best estimate until the
    real figure is recorded.

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
        float(r.amount) * (1 + category_return(r.category, flat_return) / 100) ** max(0, today_year - int(r.year))
        for r in c.itertuples()
    )
    ef = emergency_fund if emergency_fund is not None else emergency_fund_target(profile, income, today_year)
    vintage = corpus_vintage_year(income, contributions, profile.key)
    corpus_actual = corpus_potential = 0.0
    if opening and vintage is not None and today_year >= vintage:
        rate = _corpus_growth_rate(profile, targets, vintage, flat_return)
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
                    flat_return: float | None = None) -> float:
    """Lump sum to invest today to erase every *past* year's shortfall.

    For each planned year strictly before ``today_year``, the per-category
    shortfall (planned − actual) is grown to today at that category's expected
    return; surpluses in other years/categories net against it. The current
    year is deliberately excluded — its gap is "still to go this year", not
    catch-up. Never below zero, and investing more than this (overshooting the
    goal) is fine.
    """
    c = contributions[contributions["profile"] == profile.key]
    planned_fv = actual_fv = 0.0
    for y in available_years(income, contributions, profile.key):
        if y >= today_year:
            continue
        exp = expected_contributions(profile, income, targets, y)
        act = c[c["year"] == y].groupby("category")["amount"].sum().to_dict()
        for cat in set(exp) | set(act):
            grow = (1 + category_return(cat, flat_return) / 100) ** (today_year - y)
            planned_fv += exp.get(cat, 0.0) * grow
            actual_fv += act.get(cat, 0.0) * grow
    return max(0.0, planned_fv - actual_fv)


def net_worth_series(profile: Profile, income: pd.DataFrame, contributions: pd.DataFrame,
                     targets: pd.DataFrame, today_year: int,
                     ahead: int = NETWORTH_PROJECTION_YEARS,
                     opening: float = 0.0,
                     emergency_fund: float | None = None,
                     flat_return: float | None = None) -> pd.DataFrame:
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
    corpus_rate = _corpus_growth_rate(profile, targets, vintage, flat_return) if include_corpus else 0.0

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

    ef = emergency_fund if emergency_fund is not None else emergency_fund_target(profile, income, today_year)
    rows = []
    for horizon in range(first, today_year + ahead + 1):
        potential = basis = ef
        for y in range(first, horizon + 1):
            for cat, amt in streams.get(y, {}).items():
                potential += amt * (1 + category_return(cat, flat_return) / 100) ** (horizon - y)
                basis += amt
        if include_corpus and horizon >= vintage:
            basis += opening
            potential += opening * (1 + corpus_rate / 100) ** (horizon - vintage)
        rows.append({"year": horizon, "cost_basis": round(basis), "potential": round(potential),
                     "is_projected": horizon > today_year})
    return pd.DataFrame(rows)


def _default_fmt(value: float) -> str:
    """A plain ₹ formatter with thousands grouping, for callers that don't
    pass their own (see ``health_checks``)."""
    return f"₹{value:,.0f}"


def health_checks(profile: Profile, income: pd.DataFrame, targets: pd.DataFrame,
                  contributions: pd.DataFrame, adjustments: pd.DataFrame,
                  today: dt.date | None = None,
                  fmt: Callable[[float], str] | None = None) -> list[str]:
    """Plain-language data-health nudges for one person; empty when healthy.

    Pure and side-effect free — a view renders whatever comes back (or
    nothing, when the list is empty). Four checks, run independently (any
    number may fire at once):

      1. The current year has no income rows at all.
      2. The current year's investing is badly behind pace: what's gone in
         so far is under half of the elapsed-year share of the goal, and the
         year is at least 3 months in (``elapsed_year_fraction`` ≥ 0.25) —
         too early in January isn't "behind" yet.
      3. No emergency fund has ever been recorded (``emergency_fund_actual``
         is 0).
      4. The current year's contribution mix drifts 15 percentage points or
         more from the current year's target, for any one category — one
         message per drifting category. (Deliberately not cumulative: targets
         are flow targets, and old years judged against a newer target would
         flag intentional target changes as drift.)

    Args:
        fmt: Formats a rupee amount for check #2's message; defaults to a
            plain ``₹12,345`` grouping. Pass ``ui.inr_short`` from a view for
            the app's compact ₹ style — formatting is a UI concern, this stays
            pure.

    Returns:
        Plain-language findings, or ``[]`` when nothing needs attention.
    """
    fmt = fmt or _default_fmt
    today = today or dt.date.today()
    year = today.year
    findings: list[str] = []

    mine_income = income[income["profile"] == profile.key]
    if mine_income[mine_income["year"] == year].empty:
        findings.append(f"No {year} income entered yet.")

    year_goal = sum(expected_contributions(profile, income, targets, year).values())
    if year_goal > 0 and elapsed_year_fraction(today) >= 0.25:
        invested_so_far = float(contributions.loc[
            (contributions["profile"] == profile.key) & (contributions["year"] == year), "amount"
        ].sum())
        expected_by_now = year_goal * elapsed_year_fraction(today)
        if invested_so_far < 0.5 * expected_by_now:
            findings.append(
                f"{year} investing is behind: {fmt(invested_so_far)} in vs "
                f"{fmt(expected_by_now)} expected by now."
            )

    if emergency_fund_actual(adjustments, profile.key) == 0:
        findings.append("Emergency fund not recorded yet — enter it on Actuals to track your buffer.")

    # Drift compares THIS year's flow against THIS year's target — targets are
    # contribution-flow targets, and judging old years against a newer target
    # would flag intentional target changes as drift.
    year_contrib = contributions[
        (contributions["profile"] == profile.key) & (contributions["year"] == year)
    ]
    total_actual = float(year_contrib["amount"].sum())
    if total_actual > 0:
        actual_pct = 100 * year_contrib.groupby("category")["amount"].sum() / total_actual
        target = resolve_target(profile, targets, year)
        for cat in sorted(set(actual_pct.index) | set(target.keys())):
            drift = actual_pct.get(cat, 0.0) - target.get(cat, 0.0)
            if abs(drift) >= 15:
                label = CATEGORY_LABELS.get(cat, cat.replace("_", " ").capitalize())
                findings.append(
                    f"{year}'s mix drifts from its target: {label} is "
                    f"{actual_pct.get(cat, 0.0):.0f}% vs target {target.get(cat, 0.0):.0f}%."
                )

    return findings


# Rent-vs-buy: money wasted, not net worth. The core philosophy — buying
# wastes registration/stamp duty (one-time), loan INTEREST (never principal,
# which is equity), and maintenance/property tax; renting wastes the rent
# itself, inflating every year. A renter's invested savings are not waste.

def emi(principal: float, annual_rate_pct: float, tenure_years: int) -> float:
    """The standard equated-monthly-instalment formula.

    Args:
        principal: Loan amount.
        annual_rate_pct: Annual interest rate, in percent (e.g. ``8.5``).
        tenure_years: Loan tenure in years.

    Returns:
        The constant monthly instalment. At 0% interest the standard formula
        divides by zero, so that case is simply ``principal / months``.
    """
    months = tenure_years * 12
    if months <= 0:
        return 0.0
    if annual_rate_pct == 0:
        return principal / months
    r = annual_rate_pct / 1200
    factor = (1 + r) ** months
    return principal * r * factor / (factor - 1)


def _amortization_by_year(principal: float, annual_rate_pct: float, tenure_years: int,
                          monthly_emi: float) -> tuple[list[float], list[float]]:
    """Splits a loan's EMIs into interest and principal, summed per year.

    A month-by-month schedule (the only way to split interest from
    principal correctly) collapsed to one interest total and one principal
    total per year of the tenure — indices ``0..tenure_years-1``.
    """
    r = annual_rate_pct / 1200
    balance = principal
    interest_by_year: list[float] = []
    principal_by_year: list[float] = []
    interest_acc = principal_acc = 0.0
    for m in range(1, tenure_years * 12 + 1):
        interest_payment = balance * r
        principal_payment = min(monthly_emi - interest_payment, balance)
        balance = max(0.0, balance - principal_payment)
        interest_acc += interest_payment
        principal_acc += principal_payment
        if m % 12 == 0:
            interest_by_year.append(interest_acc)
            principal_by_year.append(principal_acc)
            interest_acc = principal_acc = 0.0
    return interest_by_year, principal_by_year


def rent_vs_buy(price: float, down_pct: float, loan_rate_pct: float, tenure_years: int,
               registration_pct: float, maintenance_pct: float, appreciation_pct: float,
               rent_monthly: float, rent_inflation_pct: float, invest_return_pct: float,
               horizon_years: int) -> pd.DataFrame:
    """Year-by-year money-wasted comparison between buying and renting.

    One row per year 1..``horizon_years``. Buying wastes registration/stamp
    duty (once), loan interest (never principal — that's equity), and
    maintenance/property tax (``maintenance_pct`` of ``price``, flat every
    year — an approximation, since a real property-tax bill usually tracks
    assessed value). Renting wastes the rent itself, inflating at
    ``rent_inflation_pct`` every year.

    The renter is assumed to have the same monthly housing budget a buyer
    would (EMI + maintenance): whatever of that budget isn't spent on rent —
    plus the down payment and registration money never spent at all — is
    invested at ``invest_return_pct``. Once the rent (inflating) overtakes
    EMI + maintenance (fixed once the loan is repaid, since maintenance
    persists), that monthly "difference" goes negative and draws down what
    would otherwise be invested, per the same logic. Monthly amounts are
    aggregated to one lump per year and compounded yearly (an approximation:
    real contributions land monthly, so this slightly understates each
    year's compounding versus true monthly compounding).

    Columns:
        buy_wasted_cum: registration + cumulative interest paid + cumulative
            maintenance, to date.
        rent_wasted_cum: cumulative rent paid, to date.
        rent_wasted_no_invest_cum: cumulative rent plus the investment growth
            a renter forgoes by leaving the difference as idle cash — the
            opportunity cost is real waste, so it belongs on the same axis.
        interest_paid / principal_paid: that single year's EMI split, from the
            monthly amortization schedule (interest is heaviest in year 1 and
            falls as the balance amortizes; principal mirrors it).
        maintenance_paid / rent_paid: that single year's maintenance and rent.
        loan_balance: principal still outstanding at the end of the year.
        appreciation_gain: house value so far minus the price paid.
        renter_contributed: what the renter has put aside to date (down
            payment + registration never spent, plus the yearly differences)
            at face value — a renter who never invests holds exactly this.
        renter_gain: growth on the renter's invested savings (portfolio minus
            renter_contributed).
        buy_wasted_net / rent_wasted_net: the apples-to-apples pair — each
            side's waste minus the asset gain that side ends up holding
            (the buyer's appreciation; the renter's investment growth). Can go
            negative when the asset gained more than the waste.
        buy_equity: down payment + principal repaid so far + property
            appreciation on the full price (interest/maintenance/registration
            build no equity, so they're excluded here).
        renter_portfolio: down payment + registration money never spent,
            invested from year 0, plus every year's (EMI + maintenance −
            rent) difference invested from the year it occurs.
        buy_net / rent_net: each side's ASSETS — buy_equity and
            renter_portfolio verbatim. Both sides spend the same housing
            budget by construction, so assets compare directly; subtracting
            waste again would double-count (the renter's portfolio already
            paid the rent out of that budget).

    Args:
        price: Property price.
        down_pct: Down payment as % of price; the rest is financed.
        loan_rate_pct: Annual home-loan interest rate, in percent.
        tenure_years: Loan tenure in years.
        registration_pct: One-time registration + stamp duty, as % of price.
        maintenance_pct: Annual maintenance/property tax, as % of price.
        appreciation_pct: Assumed annual property appreciation, in percent.
        rent_monthly: Starting monthly rent.
        rent_inflation_pct: Annual rent inflation, in percent.
        invest_return_pct: Annual return assumed on money the renter invests.
        horizon_years: How many years to project.

    Returns:
        A DataFrame with one row per year, columns as above.
    """
    down_payment = price * down_pct / 100
    loan_principal = price - down_payment
    registration_cost = price * registration_pct / 100
    monthly_emi = emi(loan_principal, loan_rate_pct, tenure_years)
    interest_by_year, principal_by_year = _amortization_by_year(
        loan_principal, loan_rate_pct, tenure_years, monthly_emi
    )
    maintenance_annual = price * maintenance_pct / 100
    non_invested_base = down_payment + registration_cost

    rows = []
    cum_interest = cum_principal = cum_maintenance = cum_rent = 0.0
    yearly_diff: dict[int, float] = {}  # year -> that year's (EMI+maint-rent) lump

    for year in range(1, horizon_years + 1):
        idx = year - 1
        interest_this_year = interest_by_year[idx] if idx < len(interest_by_year) else 0.0
        principal_this_year = principal_by_year[idx] if idx < len(principal_by_year) else 0.0
        cum_interest += interest_this_year
        cum_principal += principal_this_year
        cum_maintenance += maintenance_annual

        rent_this_year = rent_monthly * (1 + rent_inflation_pct / 100) ** (year - 1) * 12
        cum_rent += rent_this_year
        emi_this_year = monthly_emi * 12 if year <= tenure_years else 0.0
        yearly_diff[year] = (emi_this_year + maintenance_annual) - rent_this_year

        buy_wasted_cum = registration_cost + cum_interest + cum_maintenance
        rent_wasted_cum = cum_rent
        appreciation_gain = price * (1 + appreciation_pct / 100) ** year - price
        buy_equity = down_payment + cum_principal + appreciation_gain

        renter_portfolio = non_invested_base * (1 + invest_return_pct / 100) ** year
        for k, diff in yearly_diff.items():
            renter_portfolio += diff * (1 + invest_return_pct / 100) ** (year - k)

        renter_contributed = non_invested_base + sum(yearly_diff.values())
        renter_gain = renter_portfolio - renter_contributed

        rows.append({
            "year": year,
            "buy_wasted_cum": buy_wasted_cum,
            "rent_wasted_cum": rent_wasted_cum,
            "rent_wasted_no_invest_cum": rent_wasted_cum + renter_gain,
            "interest_paid": interest_this_year,
            "principal_paid": principal_this_year,
            "maintenance_paid": maintenance_annual,
            "rent_paid": rent_this_year,
            "loan_balance": max(0.0, loan_principal - cum_principal),
            "buy_equity": buy_equity,
            "renter_portfolio": renter_portfolio,
            "appreciation_gain": appreciation_gain,
            "renter_contributed": renter_contributed,
            "renter_gain": renter_gain,
            "buy_wasted_net": buy_wasted_cum - appreciation_gain,
            "rent_wasted_net": rent_wasted_cum - renter_gain,
            "buy_net": buy_equity,
            "rent_net": renter_portfolio,
        })
    return pd.DataFrame(rows)


def max_loan_for_emi(monthly_emi_budget: float, annual_rate_pct: float,
                     tenure_years: int) -> float:
    """The largest loan a monthly EMI budget can service (inverse of ``emi``).

    Args:
        monthly_emi_budget: The EMI one can afford per month.
        annual_rate_pct: Annual loan rate, in percent.
        tenure_years: Loan tenure in years.
    """
    months = tenure_years * 12
    r = annual_rate_pct / 100 / 12
    if r == 0:
        return monthly_emi_budget * months
    return monthly_emi_budget * ((1 + r) ** months - 1) / (r * (1 + r) ** months)


def sip_for_target(target_amount: float, annual_return_pct: float, years: float) -> float:
    """The monthly SIP that grows to ``target_amount`` in ``years``.

    End-of-month contributions compounded monthly — the inverse of the standard
    SIP future-value ``FV = P·((1+r)ⁿ−1)/r``. Handles a 0% return (straight
    division). Use it for "how much a month to reach the down payment by then".

    Args:
        target_amount: The corpus to reach.
        annual_return_pct: Assumed annual return, in percent.
        years: Years to save.
    """
    n = max(1, round(years * 12))
    r = annual_return_pct / 100 / 12
    if r == 0:
        return target_amount / n
    return target_amount * r / ((1 + r) ** n - 1)


def best_buy_year(price: float, down_pct: float, loan_rate_pct: float, tenure_years: int,
                  registration_pct: float, maintenance_pct: float, appreciation_pct: float,
                  rent_monthly: float, rent_inflation_pct: float, invest_return_pct: float,
                  horizon_years: int, starting_corpus: float = 0.0,
                  monthly_saving: float = 0.0, inflation_pct: float = 0.0,
                  emi_budget: float = 0.0, corpus_deploy_pct: float = 100.0) -> pd.DataFrame:
    """Total money wasted by the horizon, for every possible year of buying.

    Renting is not a permanent state: at some point the house gets bought, and
    *when* changes the total. Buying now means interest on a big loan from day
    one and no rent; waiting means paying rent and a pricier house, but the down
    payment keeps compounding meanwhile.

    The tension is real in both directions. Waiting costs rent and buys a
    pricier house, but the corpus keeps compounding *and* keeps being added to,
    so the down payment grows and the loan — the expensive part — shrinks. An
    interior optimum exists whenever savings outrun property appreciation.

    Every option is charged for the *whole* loan, not just the part that lands
    inside the horizon. Counting only the horizon's interest would make waiting
    look free — buy in the final year and almost none of the loan falls inside
    the window, though every rupee of it still gets paid. Ownership therefore
    lasts ``tenure_years`` in each scenario, just starting later, and the
    horizon only bounds how long waiting is allowed.

    For a purchase after ``t`` years of renting:
        - rent for years 1..t, inflating at ``rent_inflation_pct``;
        - the house costs ``price`` grown at ``appreciation_pct`` for t years,
          registration scaled to that price and paid in cash;
        - the down payment is whatever the corpus can put in after registration
          (never less than ``down_pct``, never more than the whole price), so
          waiting converts compounding into a smaller loan;
        - the loan's full interest over ``tenure_years``;
        - maintenance for those same ``tenure_years`` of ownership.

    The corpus's growth is not subtracted anywhere — it already shows up as a
    smaller loan, and counting it twice would make waiting look free again.
    A year is ``feasible`` only if the corpus covers registration plus the
    minimum down payment (``cash_ok``) *and* the resulting EMI fits
    ``emi_budget`` for that year (``emi_ok``). Cash alone would approve a loan
    the household cannot service.

    Amounts are reported in today's rupees when ``inflation_pct`` is set: each
    flow is discounted from the year it is paid, so rent in year 3 and interest
    in year 25 are not added at face value.

    Assumes a ready-to-move-in property: rent stops the day the house is
    bought, with no construction gap and no pre-EMI period.

    ``t`` runs 0..``horizon_years`` inclusive, so a 15-year horizon offers
    buying now through waiting the full fifteen.

    Args:
        price: Property price today.
        down_pct: Down payment as % of the price at purchase.
        loan_rate_pct: Annual home-loan interest rate, in percent.
        tenure_years: Loan tenure in years.
        registration_pct: One-time registration + stamp duty, as % of price.
        maintenance_pct: Annual maintenance/property tax, as % of price.
        appreciation_pct: Assumed annual property appreciation, in percent.
        rent_monthly: Starting monthly rent.
        rent_inflation_pct: Annual rent inflation, in percent.
        invest_return_pct: Annual return on the corpus while it stays invested.
        horizon_years: How many years of waiting to evaluate.
        starting_corpus: Investable savings available today.
        monthly_saving: Added to the corpus every month while waiting.
        inflation_pct: General inflation. Grows maintenance year on year and
            discounts every flow back to today's rupees, so costs decades apart
            compare honestly. 0 leaves the model in nominal terms.
        emi_budget: What the household can pay as EMI today; grown at
            ``inflation_pct`` for later years. 0 skips the serviceability test.
        corpus_deploy_pct: The most of the corpus, in percent, that goes into
            the house (down payment + registration). Below 100 keeps the rest
            invested rather than draining the portfolio for a bigger down
            payment, which — realistically — pushes the cheapest year later.

    Returns:
        One row per buy year (``wait_years`` 0..horizon-1), with the price then,
        the corpus, the down payment it funds, the loan, each waste component,
        ``feasible``, and ``total_wasted``. The best choice is the feasible row
        with the smallest ``total_wasted``.
    """
    r_month = invest_return_pct / 100 / 12
    discount = 1 + inflation_pct / 100

    def pv(amount: float, year: float) -> float:
        """``amount``, paid ``year`` years from today, in today's rupees."""
        return amount / discount ** year if inflation_pct else amount

    rows = []
    for wait in range(max(1, horizon_years) + 1):
        price_then = price * (1 + appreciation_pct / 100) ** wait
        registration_cost = price_then * registration_pct / 100
        # Corpus: today's savings compounded, plus the monthly additions made
        # while waiting (standard SIP future value; flat sum at a 0% return).
        months = wait * 12
        corpus = starting_corpus * (1 + invest_return_pct / 100) ** wait
        if monthly_saving:
            corpus += (monthly_saving * (((1 + r_month) ** months - 1) / r_month)
                       if r_month else monthly_saving * months)

        min_down = price_then * down_pct / 100
        # Only part of the corpus is ever put into a house — nobody drains their
        # whole portfolio for a bigger down payment. ``corpus_deploy_pct`` caps
        # what's available; registration is paid from that same deployable pot.
        deployable = corpus * corpus_deploy_pct / 100
        available = deployable - registration_cost  # registration is paid in cash
        down_payment = min(max(available, min_down), price_then)
        loan_principal = max(0.0, price_then - down_payment)
        monthly_emi = emi(loan_principal, loan_rate_pct, tenure_years)
        interest_by_year, _ = _amortization_by_year(
            loan_principal, loan_rate_pct, tenure_years, monthly_emi
        )
        # Affordable means both: the cash is there for registration plus the
        # minimum down payment, AND the EMI fits the household budget of that
        # year. Cash alone would green-light a loan nobody can service.
        cash_ok = available >= min_down
        budget_then = emi_budget * discount ** wait if emi_budget else 0.0
        emi_ok = monthly_emi <= budget_then if emi_budget else True
        feasible = bool(cash_ok and emi_ok)

        # Every flow is discounted from the year it is actually paid: rent while
        # waiting, registration at purchase, then interest and maintenance
        # across the tenure. Without this, a rupee in 2060 counts the same as
        # one today and waiting always looks cheaper than it is.
        rent_paid = sum(
            pv(rent_monthly * (1 + rent_inflation_pct / 100) ** y * 12, y)
            for y in range(wait)
        )
        interest_paid = sum(
            pv(amount, wait + j + 1) for j, amount in enumerate(interest_by_year)
        )
        maintenance_base = price_then * maintenance_pct / 100
        maintenance_paid = sum(
            pv(maintenance_base * discount ** j, wait + j + 1)
            for j in range(tenure_years)
        )
        registration_pv = pv(registration_cost, wait)

        rows.append({
            "wait_years": wait,
            "price_then": price_then,
            "corpus": corpus,
            "down_payment": down_payment,
            "loan": loan_principal,
            "monthly_emi": monthly_emi,
            "emi_budget": budget_then,
            "cash_ok": cash_ok,
            "emi_ok": emi_ok,
            "feasible": feasible,
            "rent_paid": rent_paid,
            "registration_cost": registration_cost,
            "registration_pv": registration_pv,
            "interest_paid": interest_paid,
            "maintenance_paid": maintenance_paid,
            "total_wasted": (rent_paid + registration_pv + interest_paid
                             + maintenance_paid),
        })
    return pd.DataFrame(rows)


def rent_vs_buy_crossover_year(df: pd.DataFrame) -> int | None:
    """The first year where buying's cumulative waste drops to or below
    renting's — the point buying becomes the less wasteful choice — or
    ``None`` if that never happens within the projected horizon."""
    crossed = df[df["buy_wasted_cum"] <= df["rent_wasted_cum"]]
    return int(crossed.iloc[0]["year"]) if not crossed.empty else None
