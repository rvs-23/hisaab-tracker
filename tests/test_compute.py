import pandas as pd
import pytest

from finance_tracker import compute
from finance_tracker.models import Profile, Target
from finance_tracker.ui import inr


@pytest.fixture
def rv():
    """Rv's real target mix from the source workbook."""
    return Profile(
        key="rv",
        name="Rv",
        birth_year=1998,
        forward_increment_pct=10,
        wants_invest_pct=6,
        default_target=Target(
            short_term={"fixed_deposit": 50, "mfs": 30, "us_market": 10, "indian_stocks": 10},
            long_term={
                "mfs": 45, "gold_metals": 25, "indian_stocks": 14,
                "us_market": 10, "ppf_nps": 5, "bonds_gsec_aif": 1,
            },
        ),
    )


@pytest.fixture
def targets():
    """Empty per-year overrides — everything falls back to default_target."""
    from finance_tracker import storage
    return pd.DataFrame(columns=storage.TARGETS_COLUMNS)


@pytest.fixture
def budget():
    """Rv's 2024 + 2025 rows (precise monthly rupee figures)."""
    return pd.DataFrame(
        [
            {"profile": "rv", "year": 2024, "starting_salary": 1107389, "job_change": "No",
             "ending_salary": 1425283, "monthly_needs": 51439, "monthly_wants": 35632,
             "monthly_investment": 31702},
            {"profile": "rv", "year": 2025, "starting_salary": 1425283, "job_change": "Yes",
             "ending_salary": 3571045, "monthly_needs": 87202, "monthly_wants": 89276,
             "monthly_investment": 121109},
        ]
    )


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


def test_split_pct_wants_is_exactly_30(rv, budget):
    pct = compute.split_pct(budget.iloc[0])
    assert pct["wants"] == pytest.approx(30, abs=0.01)
    assert sum(pct.values()) == pytest.approx(100, abs=0.01)


def test_expected_reproduces_source_sheet(rv, budget, targets):
    """The whole reason the model exists — match the spreadsheet to the rupee."""
    exp = compute.expected_contributions(rv, budget, targets, 2024)
    sheet = {
        "us_market": 40608.0, "indian_stocks": 55825.0, "mfs": 178887.7,
        "fixed_deposit": 12827.5, "ppf_nps": 19021.2, "bonds_gsec_aif": 3804.2,
        "gold_metals": 95106.2,
    }
    for cat, want in sheet.items():
        assert exp[cat] == pytest.approx(want, abs=1.0), cat


def test_pct_goal_achieved_matches_sheet(rv, budget, targets, contributions):
    pva = compute.plan_vs_actual(rv, budget, targets, contributions, 2024)
    assert compute.pct_goal_achieved(pva) == pytest.approx(76.78, abs=0.05)


def test_per_year_target_override_changes_expected(rv, budget, contributions):
    """An override row for 2024 should replace the default mix for that year."""
    override = pd.DataFrame(
        [
            {"profile": "rv", "year": 2024, "tier": "long_term", "category": "mfs", "pct": 100},
            {"profile": "rv", "year": 2024, "tier": "short_term", "category": "mfs", "pct": 100},
        ]
    )
    exp = compute.expected_contributions(rv, budget, override, 2024)
    # All investment + wants-invest money now lands in mfs, nothing in us_market.
    assert exp.get("us_market", 0) == 0
    assert exp["mfs"] == pytest.approx(31702 * 12 + 35632 * 12 * 6 / 100, abs=1.0)


def test_plan_vs_actual_shortfall(rv, budget, targets, contributions):
    pva = compute.plan_vs_actual(rv, budget, targets, contributions, 2024).set_index("category")
    # us_market: actual 39345.5 - expected 40607.9 = -1262.4 (matches sheet -1262.5)
    assert pva.loc["us_market", "shortfall"] == pytest.approx(-1262.5, abs=1.0)
    # indian_stocks over-invested: 95078 - 55824.9 = +39253
    assert pva.loc["indian_stocks", "shortfall"] == pytest.approx(39253.0, abs=1.0)


def test_projection_cumulative(rv, budget):
    proj = compute.projection(rv, budget)
    assert list(proj["year"]) == [2024, 2025]
    assert list(proj["age"]) == [26, 27]
    assert proj["invested_this_year"].iloc[0] == 31702 * 12
    assert proj["cumulative_invested"].iloc[1] == 31702 * 12 + 121109 * 12


def test_household_sums_actuals_across_people(rv, budget, targets, contributions):
    bob = Profile(
        key="bob", name="Bob", birth_year=1990, forward_increment_pct=5, wants_invest_pct=0,
        default_target=rv.default_target,
    )
    budget2 = pd.concat([budget, budget.assign(profile="bob")], ignore_index=True)
    contrib2 = pd.concat([contributions, contributions.assign(profile="bob")], ignore_index=True)
    house = compute.household_plan_vs_actual([rv, bob], budget2, targets, contrib2, 2024)
    solo = compute.plan_vs_actual(rv, budget, targets, contributions, 2024)
    assert house["actual"].sum() == pytest.approx(2 * solo["actual"].sum())


def test_available_years(budget, contributions):
    assert compute.available_years(budget, contributions) == [2024, 2025]


def test_inr_indian_grouping():
    assert inr(1234567) == "₹12,34,567"
    assert inr(999) == "₹999"
    assert inr(-45000) == "-₹45,000"
