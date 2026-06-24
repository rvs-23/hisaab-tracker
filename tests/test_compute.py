import datetime as dt

import pandas as pd
import pytest

import compute
import storage
from models import Profile
from ui import inr

TODAY = dt.date(2026, 6, 12)


@pytest.fixture
def rv():
    return Profile(
        key="rv", name="Rv", birth_year=1998, forward_increment_pct=5,
        default_target={"mfs": 45, "gold_metals": 25, "indian_stocks": 14,
                        "us_market": 10, "ppf_nps": 5, "bonds_gsec_aif": 1},
    )


@pytest.fixture
def income():
    """Rv's real income — anchor year 2023. One row per year (month=1) is enough
    for the math; compute aggregates monthly→yearly anyway."""
    return pd.DataFrame(
        [
            {"profile": "rv", "year": 2023, "month": 1, "salary": 1107389, "bonus": 0, "other": 0, "job_change": 0},
            {"profile": "rv", "year": 2024, "month": 1, "salary": 1425283, "bonus": 0, "other": 0, "job_change": 0},
            {"profile": "rv", "year": 2025, "month": 1, "salary": 3571045, "bonus": 0, "other": 0, "job_change": 1},
            {"profile": "rv", "year": 2026, "month": 1, "salary": 5076912, "bonus": 500000, "other": 0, "job_change": 0},
        ]
    )


@pytest.fixture
def targets():
    return pd.DataFrame(columns=storage.TARGETS_COLUMNS)


@pytest.fixture
def contributions():
    return pd.DataFrame(
        [
            {"year": 2024, "profile": "rv", "category": "us_market", "amount": 39345.5, "notes": None},
            {"year": 2024, "profile": "rv", "category": "indian_stocks", "amount": 95078, "notes": None},
            {"year": 2024, "profile": "rv", "category": "mfs", "amount": 169766, "notes": None},
            {"year": 2024, "profile": "rv", "category": "ppf_nps", "amount": 7600, "notes": None},
        ]
    )


def test_budget_derives_from_income_philosophy(rv, income):
    """Anchor 50/30/20, then increment 20/30/50 — must match the source sheet."""
    bs = compute.budget_series(rv, income, today=TODAY).set_index("year")
    assert bs.loc[2023, "monthly_investment"] == 18456   # 1107389*20%/12
    assert bs.loc[2024, "monthly_investment"] == 31702
    assert bs.loc[2025, "monthly_investment"] == 121109
    assert bs.loc[2026, "monthly_investment"] == 204687
    # wants is a flat 30% in every year under this philosophy
    assert compute.split_pct(bs.loc[2024])["wants"] == pytest.approx(30, abs=0.1)


def test_budget_projects_to_current_plus_three(rv, income):
    """Entered 2023–26, current year 2026 → projected 2027–29 at 5% growth."""
    bs = compute.budget_series(rv, income, today=TODAY).set_index("year")
    assert list(bs.index) == [2023, 2024, 2025, 2026, 2027, 2028, 2029]
    assert not bs.loc[2026, "is_projected"]
    assert bs.loc[2027, "is_projected"]
    # 2027 income = 5576912 * 1.05; the raise splits 20/30/50
    assert bs.loc[2027, "total_income"] == round(5576912 * 1.05)
    raise_ = 5576912 * 0.05
    assert bs.loc[2027, "investment"] == pytest.approx(
        bs.loc[2026, "investment"] + raise_ * 0.5, abs=2
    )


def test_targets_carry_forward(rv, income):
    """A 2025 override applies to 2026+ until replaced; earlier years use default."""
    override = pd.DataFrame(
        [{"profile": "rv", "year": 2025, "category": "mfs", "pct": 100}]
    )
    assert compute.resolve_target(rv, override, 2026) == {"mfs": 100}
    assert compute.resolve_target(rv, override, 2024) == rv.default_target  # before the override


def test_expected_is_investment_times_target(rv, income, targets):
    """The goal is the year's investment amount split by the target allocation."""
    bs = compute.budget_series(rv, income).set_index("year")
    investment = bs.loc[2024, "investment"]  # 380424
    exp = compute.expected_contributions(rv, income, targets, 2024)
    for cat, pct in rv.default_target.items():
        assert exp[cat] == pytest.approx(investment * pct / 100, abs=1.0), cat
    assert sum(exp.values()) == pytest.approx(investment, abs=1.0)  # 100% of investment


def test_pct_goal_achieved_matches_sheet(rv, income, targets, contributions):
    pva = compute.plan_vs_actual(rv, income, targets, contributions, 2024)
    assert compute.pct_goal_achieved(pva) == pytest.approx(81.96, abs=0.05)


def test_per_year_target_override_changes_expected(rv, income, contributions):
    override = pd.DataFrame([{"profile": "rv", "year": 2024, "category": "mfs", "pct": 100}])
    exp = compute.expected_contributions(rv, income, override, 2024)
    assert exp.get("us_market", 0) == 0  # everything now lands in mfs
    assert exp["mfs"] == pytest.approx(380424, abs=2)  # the whole 2024 investment


def test_plan_vs_actual_shortfall(rv, income, targets, contributions):
    pva = compute.plan_vs_actual(rv, income, targets, contributions, 2024).set_index("category")
    # us_market: actual 39345.5 - expected 38042.5 = +1303 (surplus)
    assert pva.loc["us_market", "shortfall"] == pytest.approx(1303.0, abs=1.0)
    # indian_stocks: 95078 - 53259.5 = +41818.5
    assert pva.loc["indian_stocks", "shortfall"] == pytest.approx(41818.5, abs=1.0)


def test_bonus_counts_toward_income_split(rv, income):
    """2026 includes a 500k bonus — it must flow through the increment split."""
    bs = compute.budget_series(rv, income).set_index("year")
    assert bs.loc[2026, "total_income"] == 5576912


def test_monthly_rows_aggregate_to_yearly(rv):
    """12 monthly rows must sum to the same annual total as one lump row."""
    monthly = pd.DataFrame(
        [{"profile": "rv", "year": 2024, "month": m, "salary": 100000, "bonus": 0, "other": 0, "job_change": 0}
         for m in range(1, 13)]
    )
    bs = compute.budget_series(rv, monthly).set_index("year")
    assert bs.loc[2024, "total_income"] == 1200000


def test_bonus_and_other_count_as_income(rv):
    row = {"profile": "rv", "year": 2024, "month": 1, "salary": 1000000, "bonus": 100000, "other": 50000, "job_change": 0}
    bs = compute.budget_series(rv, pd.DataFrame([row])).set_index("year")
    assert bs.loc[2024, "total_income"] == 1150000


def test_job_change_and_yoy_surface_in_budget(rv, income):
    bs = compute.budget_series(rv, income).set_index("year")
    assert bool(bs.loc[2025, "job_change"]) is True
    assert bool(bs.loc[2024, "job_change"]) is False
    # 2025 income 35.71L vs 2024 14.25L is a ~150% jump
    assert bs.loc[2025, "yoy"] == pytest.approx(150.55, abs=0.1)


def test_household_sums_actuals_across_people(rv, income, targets, contributions):
    bob = Profile(
        key="bob", name="Bob", birth_year=1990, forward_increment_pct=5,
        default_target=rv.default_target,
    )
    income2 = pd.concat([income, income.assign(profile="bob")], ignore_index=True)
    contrib2 = pd.concat([contributions, contributions.assign(profile="bob")], ignore_index=True)
    house = compute.household_plan_vs_actual([rv, bob], income2, targets, contrib2, 2024)
    solo = compute.plan_vs_actual(rv, income, targets, contributions, 2024)
    assert house["actual"].sum() == pytest.approx(2 * solo["actual"].sum())


def test_available_years(income, contributions):
    assert compute.available_years(income, contributions) == [2023, 2024, 2025, 2026]


def test_available_years_scopes_to_profile(income, contributions):
    """After routing, a caller can ask for just one person's years."""
    inc2 = pd.concat([income, income.assign(profile="cheeni", year=2099)], ignore_index=True)
    assert compute.available_years(inc2, contributions, "rv") == [2023, 2024, 2025, 2026]
    assert compute.available_years(inc2, contributions, "cheeni") == [2099]
    assert 2099 in compute.available_years(inc2, contributions)  # unscoped sees both


def test_selectable_years_locked_from_baseline(income, contributions):
    """Every selector offers a locked range from 2022 up to the current year."""
    yrs = compute.selectable_years(income, contributions, "rv", today=dt.date(2026, 6, 1))
    assert yrs == list(range(2022, 2027))  # 2022 floor, 2026 current


def test_emergency_fund_is_six_months_of_needs(rv, income):
    bs = compute.budget_series(rv, income).set_index("year")
    assert compute.emergency_fund_target(rv, income, 2024) == pytest.approx(6 * bs.loc[2024, "monthly_needs"])
    # No income → no budget → no emergency fund.
    assert compute.emergency_fund_target(rv, pd.DataFrame(columns=storage.INCOME_COLUMNS)) == 0.0


def test_net_worth_compounds_at_category_return(rv):
    contrib = pd.DataFrame([{"year": 2020, "profile": "rv", "category": "mfs", "amount": 100000, "notes": None}])
    no_income = pd.DataFrame(columns=storage.INCOME_COLUMNS)  # → emergency fund 0
    actual, potential = compute.net_worth_to_date(rv, no_income, contrib, today_year=2025)
    assert actual == 100000  # cost basis, no emergency fund
    assert potential == round(100000 * 1.115 ** 5)  # mfs at 11.5% for 5 years


def test_net_worth_adds_derived_emergency_fund(rv, income):
    contrib = pd.DataFrame([{"year": 2026, "profile": "rv", "category": "mfs", "amount": 50000, "notes": None}])
    ef = compute.emergency_fund_target(rv, income, 2026)
    actual, potential = compute.net_worth_to_date(rv, income, contrib, today_year=2026)
    assert actual == round(50000 + ef)   # 50k invested + EF, no growth yet (same year)
    assert potential == round(50000 + ef)


def test_net_worth_series_projects_ahead(rv, income, targets, contributions):
    s = compute.net_worth_series(rv, income, contributions, targets, today_year=2025, ahead=5)
    assert int(s["year"].max()) == 2030  # 2025 + 5
    assert s["is_projected"].sum() == 5
    assert (s["potential"] >= s["cost_basis"]).all()  # growth never below cost


# --- catch-up amount -------------------------------------------------------

def _one_year(salary=1000000):
    income = pd.DataFrame([{"profile": "rv", "year": 2024, "month": 1,
                            "salary": salary, "bonus": 0, "other": 0, "job_change": 0}])
    targets = pd.DataFrame([{"profile": "rv", "year": 2024, "category": "mfs", "pct": 100}])
    return income, targets  # anchor year → investment is 20% of salary, all in mfs


def test_catch_up_grows_shortfall_to_today(rv):
    income, targets = _one_year()  # 2024 investment 200000, all mfs, nothing invested
    no_contrib = pd.DataFrame(columns=storage.CONTRIB_COLUMNS)
    cu = compute.catch_up_amount(rv, income, targets, no_contrib, today_year=2026)
    assert cu == pytest.approx(200000 * 1.115 ** 2, rel=1e-6)  # shortfall grown 2 yrs at 11.5%


def test_catch_up_zero_when_plan_met(rv):
    income, targets = _one_year()
    contrib = pd.DataFrame([{"year": 2024, "profile": "rv", "category": "mfs", "amount": 200000, "notes": None}])
    assert compute.catch_up_amount(rv, income, targets, contrib, today_year=2026) == 0.0


def test_catch_up_zero_when_overshot(rv):
    income, targets = _one_year()
    contrib = pd.DataFrame([{"year": 2024, "profile": "rv", "category": "mfs", "amount": 500000, "notes": None}])
    assert compute.catch_up_amount(rv, income, targets, contrib, today_year=2026) == 0.0


def test_inr_indian_grouping():
    assert inr(1234567) == "₹12,34,567"
    assert inr(999) == "₹999"
    assert inr(-45000) == "-₹45,000"


# --- storage validation guards (hand-edit safety) --------------------------

@pytest.fixture
def config():
    from models import Config
    return Config(usd_inr_rate=84.0, usd_inr_as_of=dt.date(2026, 6, 1),
                  categories=["mfs", "gold_metals", "indian_stocks", "us_market",
                              "ppf_nps", "bonds_gsec_aif", "fixed_deposit"])


def test_load_missing_csvs_returns_empty(tmp_path, rv, config):
    """A fresh folder with no history CSVs loads as empty, not a crash."""
    assert storage.load_income(tmp_path, [rv]).empty
    assert storage.load_contributions(tmp_path, config, [rv]).empty
    assert storage.load_targets(tmp_path, config, [rv]).empty


def test_income_rejects_negative_and_duplicates(rv):
    base = {"profile": "rv", "year": 2024, "month": 1, "salary": 100, "bonus": 0, "other": 0, "job_change": 0}
    with pytest.raises(ValueError, match="negative"):
        storage.validate_income(pd.DataFrame([{**base, "salary": -1}]), [rv])
    with pytest.raises(ValueError, match="duplicate"):
        storage.validate_income(pd.DataFrame([base, dict(base)]), [rv])


def test_contributions_reject_negative_amount(rv, config):
    df = pd.DataFrame([{"year": 2024, "profile": "rv", "category": "mfs", "amount": -5, "notes": None}])
    with pytest.raises(ValueError, match="negative"):
        storage.validate_contributions(df, config, [rv])


def test_contributions_reject_non_numeric_amount(rv, config):
    """A typo in a hand-edited amount must fail loudly, not coerce to NaN."""
    df = pd.DataFrame([{"year": 2024, "profile": "rv", "category": "mfs", "amount": "abc", "notes": None}])
    with pytest.raises(ValueError, match="non-numeric"):
        storage.validate_contributions(df, config, [rv])


def test_targets_reject_duplicate_category(rv, config):
    df = pd.DataFrame([{"profile": "rv", "year": 2024, "category": "mfs", "pct": 50},
                       {"profile": "rv", "year": 2024, "category": "mfs", "pct": 50}])
    with pytest.raises(ValueError, match="duplicate"):
        storage.validate_targets(df, config, [rv])


def test_save_contributions_preserves_other_profile(tmp_path, rv, config):
    """The Actuals merge-back: editing one person must not drop the other's rows."""
    cheeni = Profile(key="cheeni", name="Cheeni", birth_year=1998,
                     forward_increment_pct=5, default_target=rv.default_target)
    existing = pd.DataFrame([
        {"year": 2024, "profile": "rv", "category": "mfs", "amount": 100, "notes": None},
        {"year": 2024, "profile": "cheeni", "category": "mfs", "amount": 200, "notes": None},
    ])
    storage.save_contributions(tmp_path, existing)
    # rv edits only their own row (the editor hides the profile column); merge back.
    edited = pd.DataFrame([{"year": 2024, "category": "mfs", "amount": 150, "notes": None}]).assign(profile="rv")
    others = existing[existing["profile"] != "rv"]
    combined = pd.concat([others, edited], ignore_index=True)[storage.CONTRIB_COLUMNS]
    storage.validate_contributions(combined, config, [rv, cheeni])
    storage.save_contributions(tmp_path, combined)
    reloaded = storage.load_contributions(tmp_path, config, [rv, cheeni])
    assert reloaded.loc[reloaded["profile"] == "cheeni", "amount"].iloc[0] == 200  # untouched
    assert reloaded.loc[reloaded["profile"] == "rv", "amount"].iloc[0] == 150       # updated
