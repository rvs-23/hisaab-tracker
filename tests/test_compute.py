import datetime as dt
import json

import pandas as pd
import pytest

import audit
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
    """rv's splits: anchor 50/25/25, increment 25/25/50 (per-person since 2026-07-19)."""
    bs = compute.budget_series(rv, income, today=TODAY).set_index("year")
    assert bs.loc[2023, "monthly_investment"] == 23071   # 1107389*25%/12
    assert bs.loc[2024, "monthly_investment"] == 36316
    assert bs.loc[2025, "monthly_investment"] == 125723
    assert bs.loc[2026, "monthly_investment"] == 209301
    # wants is flat at rv's base share in every year under this philosophy
    assert compute.split_pct(bs.loc[2024])["wants"] == pytest.approx(25, abs=0.1)


def test_splits_are_per_profile(rv):
    """rv anchors at 25% investment, cheeni at 30% (config.PROFILE_BASE_SPLITS)."""
    cheeni = Profile(key="cheeni", name="Cheeni", birth_year=1998,
                     forward_increment_pct=5, default_target={"mfs": 100})
    row = {"year": 2024, "month": 1, "salary": 1000000, "bonus": 0, "other": 0, "job_change": 0}
    rv_bs = compute.budget_series(rv, pd.DataFrame([{**row, "profile": "rv"}]), today=TODAY).set_index("year")
    ch_bs = compute.budget_series(cheeni, pd.DataFrame([{**row, "profile": "cheeni"}]), today=TODAY).set_index("year")
    assert rv_bs.loc[2024, "investment"] == 250000
    assert ch_bs.loc[2024, "investment"] == 300000


def test_zero_income_year_cannot_steal_the_anchor(rv, income):
    """An all-zero 2022 row (the pickers offer 2022 as a zero floor) must not
    become the anchor — 2023 keeps rv's golden anchor split."""
    zeros = pd.DataFrame(
        [{"profile": "rv", "year": 2022, "month": m, "salary": 0, "bonus": 0, "other": 0, "job_change": 0}
         for m in range(1, 13)]
    )
    bs = compute.budget_series(rv, pd.concat([zeros, income]), today=TODAY).set_index("year")
    assert 2022 not in bs.index
    assert bs.loc[2023, "monthly_investment"] == 23071  # unchanged golden anchor


def test_mid_series_zero_year_is_skipped(rv):
    rows = pd.DataFrame([
        {"profile": "rv", "year": 2023, "month": 1, "salary": 1200000, "bonus": 0, "other": 0, "job_change": 0},
        {"profile": "rv", "year": 2024, "month": 1, "salary": 0, "bonus": 0, "other": 0, "job_change": 0},
        {"profile": "rv", "year": 2025, "month": 1, "salary": 1500000, "bonus": 0, "other": 0, "job_change": 0},
    ])
    bs = compute.budget_series(rv, rows, today=TODAY).set_index("year")
    assert 2024 not in bs.index
    # 2025's increment is measured against 2023, the last earning year.
    assert bs.loc[2025, "investment"] == round(1200000 * 0.25 + 300000 * 0.50)


def test_income_drop_scales_budget_down_proportionally(rv):
    rows = pd.DataFrame([
        {"profile": "rv", "year": 2023, "month": 1, "salary": 1000000, "bonus": 0, "other": 0, "job_change": 0},
        {"profile": "rv", "year": 2024, "month": 1, "salary": 800000, "bonus": 0, "other": 0, "job_change": 0},
    ])
    bs = compute.budget_series(rv, rows, today=TODAY).set_index("year")
    # 20% drop shrinks every bucket by 20% — never negative, still sums to total.
    assert bs.loc[2024, "needs"] == round(500000 * 0.8)
    assert bs.loc[2024, "investment"] == round(250000 * 0.8)
    assert bs.loc[2024, ["needs", "wants", "investment"]].sum() == 800000


def test_all_zero_income_gives_empty_budget(rv):
    zeros = pd.DataFrame(
        [{"profile": "rv", "year": 2022, "month": 1, "salary": 0, "bonus": 0, "other": 0, "job_change": 0}]
    )
    assert compute.budget_series(rv, zeros, today=TODAY).empty


def test_budget_projects_to_current_plus_three(rv, income):
    """Entered 2023–26, current year 2026 → projected 2027–29 at 5% growth."""
    bs = compute.budget_series(rv, income, today=TODAY).set_index("year")
    assert list(bs.index) == [2023, 2024, 2025, 2026, 2027, 2028, 2029]
    assert not bs.loc[2026, "is_projected"]
    assert bs.loc[2027, "is_projected"]
    # 2027 income = 5576912 * 1.05; the raise splits per rv's increment split
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
    investment = bs.loc[2024, "investment"]  # 435794
    exp = compute.expected_contributions(rv, income, targets, 2024)
    for cat, pct in rv.default_target.items():
        assert exp[cat] == pytest.approx(investment * pct / 100, abs=1.0), cat
    assert sum(exp.values()) == pytest.approx(investment, abs=1.0)  # 100% of investment


def test_pct_goal_achieved_golden(rv, income, targets, contributions):
    """Golden for rv's 50/25/25 splits: 2024 expected 435,794 vs 311,789.5 actual."""
    pva = compute.plan_vs_actual(rv, income, targets, contributions, 2024)
    assert compute.pct_goal_achieved(pva) == pytest.approx(71.55, abs=0.05)


def test_per_year_target_override_changes_expected(rv, income, contributions):
    override = pd.DataFrame([{"profile": "rv", "year": 2024, "category": "mfs", "pct": 100}])
    exp = compute.expected_contributions(rv, income, override, 2024)
    assert exp.get("us_market", 0) == 0  # everything now lands in mfs
    assert exp["mfs"] == pytest.approx(435794, abs=2)  # the whole 2024 investment


def test_plan_vs_actual_shortfall(rv, income, targets, contributions):
    pva = compute.plan_vs_actual(rv, income, targets, contributions, 2024).set_index("category")
    # us_market: actual 39345.5 - expected 43579.4 = -4233.9 (shortfall)
    assert pva.loc["us_market", "shortfall"] == pytest.approx(-4233.9, abs=1.0)
    # indian_stocks: 95078 - 61011.2 = +34066.8 (surplus)
    assert pva.loc["indian_stocks", "shortfall"] == pytest.approx(34066.8, abs=1.0)


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


def test_negative_other_reduces_total_but_still_produces_a_budget_row(rv):
    """A large tax payment under `other` can go negative for one month; as long
    as the year's total stays positive, budget_series still produces a row for
    it, off the reduced total (not skipped like a <=0 year)."""
    row = {"profile": "rv", "year": 2026, "month": 3, "salary": 5000000, "bonus": 0,
           "other": -500000, "job_change": 0}
    bs = compute.budget_series(rv, pd.DataFrame([row])).set_index("year")
    assert 2026 in bs.index
    assert bs.loc[2026, "total_income"] == 4500000


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


def test_emergency_fund_target_is_four_months_of_needs(rv, income):
    bs = compute.budget_series(rv, income).set_index("year")
    expected = 4 * bs.loc[2024, "monthly_needs"]
    assert compute.emergency_fund_target(rv, income, 2024) == pytest.approx(expected)
    # No income → no budget → no emergency-fund target.
    assert compute.emergency_fund_target(rv, pd.DataFrame(columns=storage.INCOME_COLUMNS)) == 0.0


def test_actual_emergency_fund_overrides_target_in_net_worth(rv, income, targets, contributions):
    """An entered fund replaces the derived target in both net-worth figures."""
    with_target = compute.net_worth_to_date(rv, income, contributions, targets, 2025)
    with_actual = compute.net_worth_to_date(rv, income, contributions, targets, 2025, emergency_fund=100000)
    ef_target = compute.emergency_fund_target(rv, income, 2025)
    assert with_actual[0] == with_target[0] - round(ef_target) + 100000
    assert with_actual[1] == with_target[1] - round(ef_target) + 100000


def test_emergency_fund_adjustment_field_accepted(rv):
    df = pd.DataFrame([{"profile": "rv", "field": "emergency_fund", "value": 500000}])
    storage.validate_adjustments(df, [rv])
    assert compute.emergency_fund_actual(df, "rv") == 500000
    assert compute.emergency_fund_actual(df, "cheeni") == 0.0


def test_net_worth_compounds_at_category_return(rv, targets):
    contrib = pd.DataFrame([{"year": 2020, "profile": "rv", "category": "mfs", "amount": 100000, "notes": None}])
    no_income = pd.DataFrame(columns=storage.INCOME_COLUMNS)  # → emergency fund 0
    actual, potential = compute.net_worth_to_date(rv, no_income, contrib, targets, today_year=2025)
    assert actual == 100000  # cost basis, no emergency fund
    assert potential == round(100000 * 1.115 ** 5)  # mfs at 11.5% for 5 years


def test_net_worth_adds_derived_emergency_fund(rv, income, targets):
    contrib = pd.DataFrame([{"year": 2026, "profile": "rv", "category": "mfs", "amount": 50000, "notes": None}])
    ef = compute.emergency_fund_target(rv, income, 2026)
    actual, potential = compute.net_worth_to_date(rv, income, contrib, targets, today_year=2026)
    assert actual == round(50000 + ef)   # 50k invested + EF, no growth yet (same year)
    assert potential == round(50000 + ef)


def test_net_worth_series_projects_ahead(rv, income, targets, contributions):
    s = compute.net_worth_series(rv, income, contributions, targets, today_year=2025, ahead=5)
    assert int(s["year"].max()) == 2030  # 2025 + 5
    assert s["is_projected"].sum() == 5
    assert (s["potential"] >= s["cost_basis"]).all()  # growth never below cost


# Opening corpus (pre-tracking investments).

def test_corpus_vintage_is_first_tracked_year(income, contributions):
    """Vintage is per person: the earliest year with any income or
    contribution row — not a shared global year."""
    cheeni_income = pd.DataFrame([
        {"profile": "cheeni", "year": 2024, "month": 1, "salary": 900000, "bonus": 0, "other": 0, "job_change": 0},
    ])
    combined_income = pd.concat([income, cheeni_income], ignore_index=True)
    assert compute.corpus_vintage_year(combined_income, contributions, "rv") == 2023
    assert compute.corpus_vintage_year(combined_income, contributions, "cheeni") == 2024


def test_corpus_vintage_none_with_no_data(rv):
    no_income = pd.DataFrame(columns=storage.INCOME_COLUMNS)
    no_contrib = pd.DataFrame(columns=storage.CONTRIB_COLUMNS)
    assert compute.corpus_vintage_year(no_income, no_contrib, "rv") is None


def test_opening_corpus_reads_the_named_profile_field():
    adjustments = pd.DataFrame([
        {"profile": "rv", "field": "opening_corpus", "value": 2000000},
        {"profile": "cheeni", "field": "opening_corpus", "value": 0},
    ])
    assert compute.opening_corpus(adjustments, "rv") == 2000000
    assert compute.opening_corpus(adjustments, "cheeni") == 0
    assert compute.opening_corpus(pd.DataFrame(columns=storage.ADJUSTMENTS_COLUMNS), "rv") == 0.0


def test_net_worth_to_date_grows_corpus_from_vintage(rv, targets):
    """A zero-salary income row anchors the vintage at 2023 without pulling in
    an emergency fund, isolating the corpus's own growth to 2025."""
    zero_income = pd.DataFrame([
        {"profile": "rv", "year": 2023, "month": 1, "salary": 0, "bonus": 0, "other": 0, "job_change": 0}
    ])
    no_contrib = pd.DataFrame(columns=storage.CONTRIB_COLUMNS)
    actual, potential = compute.net_worth_to_date(
        rv, zero_income, no_contrib, targets, today_year=2025, opening=100000)
    rate = sum(pct / 100 * compute.EXPECTED_RETURNS.get(cat, 0) for cat, pct in rv.default_target.items())
    assert actual == 100000  # face value; zero income → no budget row → no EF
    assert potential == round(100000 * (1 + rate / 100) ** (2025 - 2023))


def test_net_worth_to_date_excludes_corpus_before_vintage(rv, targets):
    """today_year before the vintage year: corpus contributes nothing."""
    zero_income = pd.DataFrame([
        {"profile": "rv", "year": 2024, "month": 1, "salary": 0, "bonus": 0, "other": 0, "job_change": 0}
    ])
    no_contrib = pd.DataFrame(columns=storage.CONTRIB_COLUMNS)
    actual, potential = compute.net_worth_to_date(
        rv, zero_income, no_contrib, targets, today_year=2023, opening=100000)
    assert actual == 0  # today_year (2023) < vintage (2024) → nothing counted
    assert potential == 0


def test_net_worth_to_date_no_data_ignores_corpus(rv):
    """No income or contributions at all → no vintage to anchor to → the
    corpus contributes nothing even though a value was entered."""
    no_income = pd.DataFrame(columns=storage.INCOME_COLUMNS)
    no_contrib = pd.DataFrame(columns=storage.CONTRIB_COLUMNS)
    targets = pd.DataFrame(columns=storage.TARGETS_COLUMNS)
    actual, potential = compute.net_worth_to_date(
        rv, no_income, no_contrib, targets, today_year=2025, opening=100000)
    assert actual == 0
    assert potential == 0


def test_net_worth_series_extends_to_vintage_when_corpus_present(rv, income, targets, contributions):
    """rv's contributions start 2024, but income (and so the corpus's
    vintage) starts 2023. With no corpus, the series starts at the first
    contribution year; with one, it must reach back to the vintage."""
    without = compute.net_worth_series(rv, income, contributions, targets, today_year=2025, ahead=1)
    assert without["year"].min() == 2024

    with_corpus = compute.net_worth_series(
        rv, income, contributions, targets, today_year=2025, ahead=1, opening=100000
    ).set_index("year")
    assert with_corpus.index.min() == 2023

    ef = compute.emergency_fund_target(rv, income, 2025)
    assert with_corpus.loc[2023, "cost_basis"] == round(ef + 100000)  # EF + corpus face value only
    assert with_corpus.loc[2023, "potential"] == pytest.approx(ef + 100000, abs=1)  # vintage year, no growth yet

    rate = sum(pct / 100 * compute.EXPECTED_RETURNS.get(cat, 0) for cat, pct in rv.default_target.items())
    grown = 100000 * (1 + rate / 100) ** (2025 - 2023)
    without_2025 = without.set_index("year").loc[2025, "potential"]
    assert with_corpus.loc[2025, "potential"] == pytest.approx(without_2025 + grown, abs=1)


def test_net_worth_series_zero_opening_is_a_no_op(rv, income, targets, contributions):
    """opening=0.0 (the default) must reproduce the pre-corpus behaviour exactly."""
    with_zero = compute.net_worth_series(rv, income, contributions, targets, today_year=2025, ahead=2, opening=0.0)
    without = compute.net_worth_series(rv, income, contributions, targets, today_year=2025, ahead=2)
    pd.testing.assert_frame_equal(with_zero, without)


def test_catch_up_unaffected_by_opening_corpus(rv):
    """Catch-up must not see the corpus at all — it isn't threaded through."""
    income, targets = _one_year()
    no_contrib = pd.DataFrame(columns=storage.CONTRIB_COLUMNS)
    cu = compute.catch_up_amount(rv, income, targets, no_contrib, today_year=2026)
    assert cu == pytest.approx(250000 * 1.115 ** 2, rel=1e-6)  # identical to the no-corpus test


# Catch-up amount.

def _one_year(salary=1000000):
    income = pd.DataFrame([{"profile": "rv", "year": 2024, "month": 1,
                            "salary": salary, "bonus": 0, "other": 0, "job_change": 0}])
    targets = pd.DataFrame([{"profile": "rv", "year": 2024, "category": "mfs", "pct": 100}])
    return income, targets  # anchor year → investment is 25% of rv's salary, all in mfs


def test_catch_up_grows_shortfall_to_today(rv):
    income, targets = _one_year()  # 2024 investment 250000, all mfs, nothing invested
    no_contrib = pd.DataFrame(columns=storage.CONTRIB_COLUMNS)
    cu = compute.catch_up_amount(rv, income, targets, no_contrib, today_year=2026)
    assert cu == pytest.approx(250000 * 1.115 ** 2, rel=1e-6)  # shortfall grown 2 yrs at 11.5%


def test_catch_up_zero_when_plan_met(rv):
    income, targets = _one_year()
    contrib = pd.DataFrame([{"year": 2024, "profile": "rv", "category": "mfs", "amount": 250000, "notes": None}])
    assert compute.catch_up_amount(rv, income, targets, contrib, today_year=2026) == 0.0


def test_catch_up_zero_when_overshot(rv):
    income, targets = _one_year()
    contrib = pd.DataFrame([{"year": 2024, "profile": "rv", "category": "mfs", "amount": 500000, "notes": None}])
    assert compute.catch_up_amount(rv, income, targets, contrib, today_year=2026) == 0.0


def test_elapsed_year_fraction_midyear_is_about_half():
    assert compute.elapsed_year_fraction(dt.date(2027, 7, 2)) == pytest.approx(0.5, abs=0.01)


def test_elapsed_year_fraction_endpoints():
    assert compute.elapsed_year_fraction(dt.date(2025, 1, 1)) == pytest.approx(1 / 365, abs=1e-6)
    assert compute.elapsed_year_fraction(dt.date(2025, 12, 31)) == pytest.approx(1.0, abs=1e-6)


def test_catch_up_excludes_the_current_year(rv):
    """Catch-up is past years only — the current year's gap is 'left to go',
    not catch-up (2026-07-19: Rv's definition)."""
    income, targets = _one_year()  # the only planned year is 2024
    no_contrib = pd.DataFrame(columns=storage.CONTRIB_COLUMNS)
    assert compute.catch_up_amount(rv, income, targets, no_contrib, today_year=2024) == 0.0


def test_catch_up_counts_a_year_once_it_is_past(rv):
    income, targets = _one_year()  # shortfall lives in 2024
    no_contrib = pd.DataFrame(columns=storage.CONTRIB_COLUMNS)
    cu = compute.catch_up_amount(rv, income, targets, no_contrib, today_year=2025)
    assert cu == pytest.approx(250000 * 1.115, rel=1e-6)  # grown one year


def test_inr_indian_grouping():
    assert inr(1234567) == "₹12,34,567"
    assert inr(999) == "₹999"
    assert inr(-45000) == "-₹45,000"


# Storage validation guards (hand-edit safety).

@pytest.fixture
def config():
    from models import Config
    return Config(categories=["mfs", "gold_metals", "indian_stocks", "us_market",
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


def test_income_other_may_be_negative(rv):
    """`other` is the catch-all (tax payments, clawbacks) and may go negative;
    salary and bonus must stay non-negative."""
    base = {"profile": "rv", "year": 2024, "month": 1, "salary": 100, "bonus": 0, "other": 0, "job_change": 0}
    storage.validate_income(pd.DataFrame([{**base, "other": -500000}]), [rv])  # does not raise
    with pytest.raises(ValueError, match="negative"):
        storage.validate_income(pd.DataFrame([{**base, "salary": -1}]), [rv])
    with pytest.raises(ValueError, match="negative"):
        storage.validate_income(pd.DataFrame([{**base, "bonus": -1}]), [rv])


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


def _income_row(salary=100):
    return pd.DataFrame([{"profile": "rv", "year": 2024, "month": 1, "salary": salary,
                          "bonus": 0, "other": 0, "job_change": 0}])


def test_save_appends_audit_log(tmp_path, rv):
    storage.save_income(tmp_path, _income_row())
    lines = (tmp_path / audit.CHANGES_LOG).read_text().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["file"] == "income.csv"
    assert rec["touched"] == [["rv", 2024]]
    assert rec["rows_after"] == 1
    assert len(rec["added"]) == 1 and rec["removed"] == []
    assert "ts" in rec


def test_noop_save_logs_nothing(tmp_path, rv):
    storage.save_income(tmp_path, _income_row())
    storage.save_income(tmp_path, _income_row())  # identical re-save
    lines = (tmp_path / audit.CHANGES_LOG).read_text().splitlines()
    assert len(lines) == 1  # second save changed nothing → not logged


def test_edit_logs_added_and_removed(tmp_path, rv):
    storage.save_income(tmp_path, _income_row(salary=100))
    storage.save_income(tmp_path, _income_row(salary=200))
    recs = [json.loads(line) for line in (tmp_path / audit.CHANGES_LOG).read_text().splitlines()]
    assert len(recs) == 2
    last = recs[-1]
    assert last["added"][0]["salary"] == 200
    assert last["removed"][0]["salary"] == 100


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


# Adjustments (opening corpus).

def test_load_missing_adjustments_returns_empty(tmp_path, rv):
    assert storage.load_adjustments(tmp_path, [rv]).empty


def test_adjustments_reject_negative_value(rv):
    df = pd.DataFrame([{"profile": "rv", "field": "opening_corpus", "value": -1}])
    with pytest.raises(ValueError, match="negative"):
        storage.validate_adjustments(df, [rv])


def test_adjustments_reject_unknown_field(rv):
    df = pd.DataFrame([{"profile": "rv", "field": "not_a_real_field", "value": 100}])
    with pytest.raises(ValueError, match="unknown fields"):
        storage.validate_adjustments(df, [rv])


def test_adjustments_reject_duplicate_profile_field(rv):
    df = pd.DataFrame([
        {"profile": "rv", "field": "opening_corpus", "value": 100},
        {"profile": "rv", "field": "opening_corpus", "value": 200},
    ])
    with pytest.raises(ValueError, match="duplicate"):
        storage.validate_adjustments(df, [rv])


def test_adjustments_reject_unknown_profile(rv):
    df = pd.DataFrame([{"profile": "someone_else", "field": "opening_corpus", "value": 100}])
    with pytest.raises(ValueError, match="unknown profiles"):
        storage.validate_adjustments(df, [rv])


def test_save_adjustments_appends_audit_log(tmp_path, rv):
    """adjustments.csv has no ``year`` column, so log_change's ``touched``
    extraction (which keys on ``year``) can't populate it — a save must still
    log the added/removed rows with ``touched`` simply empty."""
    df = pd.DataFrame([{"profile": "rv", "field": "opening_corpus", "value": 2000000}])
    storage.save_adjustments(tmp_path, df)
    lines = (tmp_path / audit.CHANGES_LOG).read_text().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["file"] == "adjustments.csv"
    assert rec["touched"] == []
    assert rec["rows_after"] == 1
    assert len(rec["added"]) == 1 and rec["added"][0]["value"] == 2000000
    assert rec["removed"] == []
