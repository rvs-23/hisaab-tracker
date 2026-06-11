import datetime as dt

import pandas as pd
import pytest

from finance_tracker import compute
from finance_tracker.models import Config, Profile, Split
from finance_tracker.ui import inr


@pytest.fixture
def profile():
    return Profile(
        key="rv",
        name="Rv",
        birth_year=1995,
        monthly_salary=100000,
        salary_increment_pct=10,
        split=Split(needs=50, wants=20, investment=30),
        projection_start_year=2026,
        projection_years=3,
    )


@pytest.fixture
def config():
    return Config(
        usd_inr_rate=80.0,
        usd_inr_as_of=dt.date(2026, 6, 1),
        categories=["zerodha_equity", "us_equity", "ppf"],
        target_mix={"zerodha_equity": 50, "us_equity": 30, "ppf": 20},
    )


@pytest.fixture
def holdings():
    return pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2026-05-01", "2026-05-01", "2026-06-01", "2026-06-01", "2026-05-15"]
            ),
            "profile": ["rv", "rv", "rv", "rv", "partner"],
            "instrument": ["Zerodha", "US", "Zerodha", "US", "PPF"],
            "category": ["zerodha_equity", "us_equity", "zerodha_equity", "us_equity", "ppf"],
            "currency": ["INR", "USD", "INR", "USD", "INR"],
            "value": [100000.0, 1000.0, 120000.0, 1000.0, 50000.0],
            "notes": [None] * 5,
        }
    )


def test_budget_split(profile):
    split = compute.budget_split(profile)
    assert split == {"needs": 50000, "wants": 20000, "investment": 30000}
    assert sum(split.values()) == profile.monthly_salary


def test_projection(profile):
    proj = compute.projection(profile)
    assert len(proj) == 3
    assert list(proj["year"]) == [2026, 2027, 2028]
    assert list(proj["age"]) == [31, 32, 33]
    # year 1: 30k/mo -> 360k; year 2 salary +10% -> 33k/mo -> 396k more
    assert proj["cumulative_invested"].iloc[0] == 360000
    assert proj["cumulative_invested"].iloc[1] == 360000 + 396000


def test_current_holdings_staggered_dates(holdings):
    current = compute.current_holdings(holdings)
    # rv's latest is 2026-06-01, partner's latest is 2026-05-15
    assert set(current.loc[current["profile"] == "rv", "date"]) == {pd.Timestamp("2026-06-01")}
    assert set(current.loc[current["profile"] == "partner", "date"]) == {
        pd.Timestamp("2026-05-15")
    }


def test_allocation_converts_usd_and_sums_to_100(holdings, config):
    alloc = compute.allocation(holdings, config)  # household
    assert alloc["pct"].sum() == pytest.approx(100)
    us = alloc.set_index("category").loc["us_equity", "value_inr"]
    assert us == 1000 * 80.0
    total = alloc["value_inr"].sum()
    assert total == 120000 + 80000 + 50000


def test_allocation_per_profile(holdings, config):
    alloc = compute.allocation(holdings, config, profile_key="partner")
    assert list(alloc["category"]) == ["ppf"]
    assert alloc["pct"].iloc[0] == pytest.approx(100)


def test_plan_vs_actual(holdings, config):
    pva = compute.plan_vs_actual(holdings, config).set_index("category")
    total = 250000
    # ppf target is 20% of 250k = 50k, actual 50k -> diff 0
    assert pva.loc["ppf", "diff_inr"] == pytest.approx(0)
    # zerodha target 125k, actual 120k -> 5k shortfall
    assert pva.loc["zerodha_equity", "diff_inr"] == pytest.approx(-5000)
    assert pva["actual_inr"].sum() == pytest.approx(total)


def test_networth_history_carries_forward(holdings, config, profile):
    profiles = [
        profile,
        Profile(
            key="partner",
            name="Partner",
            birth_year=1996,
            monthly_salary=1,
            salary_increment_pct=0,
            split=Split(needs=100, wants=0, investment=0),
            projection_start_year=2026,
            projection_years=1,
        ),
    ]
    hist = compute.networth_history(holdings, config, profiles)
    # last household value = rv latest (120k + 80k) + partner carried forward (50k)
    assert hist["Household"].iloc[-1] == pytest.approx(250000)


def test_inr_indian_grouping():
    assert inr(1234567) == "₹12,34,567"
    assert inr(999) == "₹999"
    assert inr(-45000) == "-₹45,000"
