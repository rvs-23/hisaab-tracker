"""Golden tests for compute.health_checks — each nudge firing and not firing."""

import datetime as dt

import pandas as pd
import pytest

import compute
import storage
from models import Profile

TODAY = dt.date(2026, 7, 1)  # ~50% into the year — well past the 3-month guard


@pytest.fixture
def rv():
    return Profile(
        key="rv", name="Rv", birth_year=1998, forward_increment_pct=5,
        default_target={"mfs": 60, "gold_metals": 40},
    )


@pytest.fixture
def no_income():
    return pd.DataFrame(columns=storage.INCOME_COLUMNS)


@pytest.fixture
def no_contrib():
    return pd.DataFrame(columns=storage.CONTRIB_COLUMNS)


@pytest.fixture
def no_targets():
    return pd.DataFrame(columns=storage.TARGETS_COLUMNS)


@pytest.fixture
def no_adjustments():
    return pd.DataFrame(columns=storage.ADJUSTMENTS_COLUMNS)


def _income_row(year, salary=1200000):
    return pd.DataFrame([
        {"profile": "rv", "year": year, "month": 1, "salary": salary, "bonus": 0, "other": 0, "job_change": 0}
    ])


# 1. No income entered yet for the current year.

def test_no_current_year_income_fires(rv, no_contrib, no_targets, no_adjustments):
    income = _income_row(2024)  # a past year only — nothing for 2026
    findings = compute.health_checks(rv, income, no_targets, no_contrib, no_adjustments, today=TODAY)
    assert any(f == "No 2026 income entered yet." for f in findings)


def test_current_year_income_present_does_not_fire(rv, no_contrib, no_targets, no_adjustments):
    income = _income_row(2026)
    findings = compute.health_checks(rv, income, no_targets, no_contrib, no_adjustments, today=TODAY)
    assert not any("income entered yet" in f for f in findings)


# 2. Current-year investing badly behind pace (once ≥3 months into the year).

def test_investing_behind_pace_fires(rv, no_targets, no_adjustments):
    income = _income_row(2026, salary=1200000)  # anchor year: investment = 25% = 300000
    contrib = pd.DataFrame(columns=storage.CONTRIB_COLUMNS)  # nothing invested at all
    findings = compute.health_checks(rv, income, no_targets, contrib, no_adjustments, today=TODAY)
    assert any("investing is behind" in f for f in findings)


def test_investing_on_pace_does_not_fire(rv, no_targets, no_adjustments):
    income = _income_row(2026, salary=1200000)  # investment goal 300000
    # Comfortably invested more than half the elapsed-year share.
    contrib = pd.DataFrame([
        {"year": 2026, "profile": "rv", "category": "mfs", "amount": 250000, "notes": None},
    ])
    findings = compute.health_checks(rv, income, no_targets, contrib, no_adjustments, today=TODAY)
    assert not any("investing is behind" in f for f in findings)


def test_investing_behind_does_not_fire_early_in_year(rv, no_targets, no_adjustments):
    """Under the 3-month guard, even zero invested isn't flagged yet."""
    early = dt.date(2026, 1, 15)
    income = _income_row(2026, salary=1200000)
    contrib = pd.DataFrame(columns=storage.CONTRIB_COLUMNS)
    findings = compute.health_checks(rv, income, no_targets, contrib, no_adjustments, today=early)
    assert not any("investing is behind" in f for f in findings)


def test_investing_behind_uses_custom_formatter(rv, no_targets, no_adjustments):
    income = _income_row(2026, salary=1200000)
    contrib = pd.DataFrame(columns=storage.CONTRIB_COLUMNS)
    findings = compute.health_checks(
        rv, income, no_targets, contrib, no_adjustments, today=TODAY,
        fmt=lambda v: f"RS{v:.0f}",
    )
    behind = next(f for f in findings if "investing is behind" in f)
    assert "RS" in behind and "₹" not in behind


# 3. Emergency fund never entered.

def test_no_emergency_fund_fires(rv, no_income, no_contrib, no_targets, no_adjustments):
    findings = compute.health_checks(rv, no_income, no_targets, no_contrib, no_adjustments, today=TODAY)
    assert any("Emergency fund not recorded" in f for f in findings)


def test_emergency_fund_recorded_does_not_fire(rv, no_income, no_contrib, no_targets):
    adjustments = pd.DataFrame([{"profile": "rv", "field": "emergency_fund", "value": 500000}])
    findings = compute.health_checks(rv, no_income, no_targets, no_contrib, adjustments, today=TODAY)
    assert not any("Emergency fund not recorded" in f for f in findings)


# 4. Cumulative actual mix drifts ≥15pp from target.

def test_mix_drift_fires(rv, no_income, no_targets, no_adjustments):
    """This year all-mfs vs a 60/40 target — both categories drift 40pp.
    Drift is judged on the CURRENT year's flow vs the current year's target
    (cumulative-vs-newer-target flagged intentional target changes)."""
    contrib = pd.DataFrame([
        {"year": TODAY.year, "profile": "rv", "category": "mfs", "amount": 100000, "notes": None},
    ])
    findings = compute.health_checks(rv, no_income, no_targets, contrib, no_adjustments, today=TODAY)
    drift = [f for f in findings if "drifts from its target" in f]
    assert any("Mutual funds" in f for f in drift)
    assert any("Gold" in f for f in drift)


def test_mix_drift_ignores_past_years(rv, no_income, no_targets, no_adjustments):
    """A past year's mix can't fire drift — targets are flow targets."""
    contrib = pd.DataFrame([
        {"year": TODAY.year - 2, "profile": "rv", "category": "mfs", "amount": 100000, "notes": None},
    ])
    findings = compute.health_checks(rv, no_income, no_targets, contrib, no_adjustments, today=TODAY)
    assert not [f for f in findings if "drifts" in f]


def test_mix_close_to_target_does_not_fire(rv, no_income, no_targets, no_adjustments):
    """55/45 actual vs 60/40 target — 5pp off, well under the 15pp threshold."""
    contrib = pd.DataFrame([
        {"year": 2024, "profile": "rv", "category": "mfs", "amount": 55000, "notes": None},
        {"year": 2024, "profile": "rv", "category": "gold_metals", "amount": 45000, "notes": None},
    ])
    findings = compute.health_checks(rv, no_income, no_targets, contrib, no_adjustments, today=TODAY)
    assert not any("drifts from target" in f for f in findings)


def test_no_contributions_skips_mix_check(rv, no_income, no_contrib, no_targets, no_adjustments):
    """Nothing invested yet — no basis for a drift comparison, so it's silent."""
    findings = compute.health_checks(rv, no_income, no_targets, no_contrib, no_adjustments, today=TODAY)
    assert not any("drifts from target" in f for f in findings)


# Fully healthy → empty list.

def test_fully_healthy_returns_empty_list(rv, no_targets):
    income = _income_row(2026, salary=1200000)  # current-year income present
    contrib = pd.DataFrame([  # on-pace and matching the 60/40 target
        {"year": 2026, "profile": "rv", "category": "mfs", "amount": 180000, "notes": None},
        {"year": 2026, "profile": "rv", "category": "gold_metals", "amount": 120000, "notes": None},
    ])
    adjustments = pd.DataFrame([{"profile": "rv", "field": "emergency_fund", "value": 500000}])
    findings = compute.health_checks(rv, income, no_targets, contrib, adjustments, today=TODAY)
    assert findings == []
