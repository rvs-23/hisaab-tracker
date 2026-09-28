"""Golden tests for compute.emi / compute.rent_vs_buy — the money-wasted model."""

import pytest

import compute


# EMI.

def test_emi_golden_80l_8_5pct_20y():
    """Hand-checked: ₹80L loan, 8.5% p.a., 20 years → EMI ≈ ₹69,426."""
    assert compute.emi(8_000_000, 8.5, 20) == pytest.approx(69425.86, abs=0.01)


def test_emi_zero_rate_is_flat_division():
    assert compute.emi(1_200_000, 0, 10) == pytest.approx(10_000.0)


def test_emi_zero_tenure_is_zero():
    assert compute.emi(1_000_000, 8.5, 0) == 0.0


# Amortization: interest + principal must reconstruct the EMI stream.

def test_interest_plus_principal_equals_emi_times_months():
    principal, rate, tenure = 8_000_000, 8.5, 20
    monthly = compute.emi(principal, rate, tenure)
    interest_by_year, principal_by_year = compute._amortization_by_year(
        principal, rate, tenure, monthly
    )
    total = sum(interest_by_year) + sum(principal_by_year)
    assert total == pytest.approx(monthly * tenure * 12, rel=1e-6)
    # Principal paid down over the full tenure must reconstruct the loan.
    assert sum(principal_by_year) == pytest.approx(principal, rel=1e-6)


def test_emi_matches_published_figure_50l_8_5pct_20y():
    """The most-quoted Indian home-loan example: ₹50L at 8.5% over 20y ≈ ₹43,391."""
    assert compute.emi(5_000_000, 8.5, 20) == pytest.approx(43_391.16, abs=0.01)


def test_interest_falls_and_principal_rises_every_year():
    """The defining property of an EMI: a fixed instalment on a shrinking
    balance, so interest is heaviest in year 1 and principal overtakes it."""
    principal, rate, tenure = 12_000_000, 8.5, 20
    interest, repaid = compute._amortization_by_year(
        principal, rate, tenure, compute.emi(principal, rate, tenure)
    )
    assert all(a > b for a, b in zip(interest, interest[1:]))
    assert all(a < b for a, b in zip(repaid, repaid[1:]))
    assert interest[0] > repaid[0]  # year 1 is mostly interest
    assert interest[-1] < repaid[-1]  # the final year is mostly principal
    assert len(interest) == tenure


def test_amortization_zero_rate_is_all_principal():
    principal, tenure = 1_200_000, 10
    monthly = compute.emi(principal, 0, tenure)
    interest_by_year, principal_by_year = compute._amortization_by_year(
        principal, 0, tenure, monthly
    )
    assert sum(interest_by_year) == pytest.approx(0.0, abs=1e-6)
    assert sum(principal_by_year) == pytest.approx(principal, rel=1e-6)


# rent_vs_buy — sane defaults for a metro scenario.

DEFAULTS = dict(
    price=15_000_000, down_pct=20, loan_rate_pct=8.5, tenure_years=20,
    registration_pct=7, maintenance_pct=0.5, appreciation_pct=5,
    rent_monthly=40_000, rent_inflation_pct=5, invest_return_pct=10,
    horizon_years=15,
)


def test_rent_vs_buy_returns_one_row_per_year():
    df = compute.rent_vs_buy(**DEFAULTS)
    assert list(df["year"]) == list(range(1, 16))


def test_zero_loan_rate_means_zero_interest_waste():
    params = {**DEFAULTS, "loan_rate_pct": 0}
    df = compute.rent_vs_buy(**params)
    # buy_wasted_cum at year 1 = registration + 0 interest + 1yr maintenance.
    registration = DEFAULTS["price"] * DEFAULTS["registration_pct"] / 100
    maintenance = DEFAULTS["price"] * DEFAULTS["maintenance_pct"] / 100
    assert df.iloc[0]["buy_wasted_cum"] == pytest.approx(registration + maintenance, rel=1e-6)


def test_waste_curves_are_monotonic_non_decreasing():
    df = compute.rent_vs_buy(**DEFAULTS)
    assert (df["buy_wasted_cum"].diff().dropna() >= -1e-6).all()
    assert (df["rent_wasted_cum"].diff().dropna() >= -1e-6).all()


def test_buy_equity_grows_over_time():
    """Principal repayment + appreciation should only ever push equity up."""
    df = compute.rent_vs_buy(**DEFAULTS)
    assert (df["buy_equity"].diff().dropna() >= -1e-6).all()
    assert df["buy_equity"].iloc[-1] > df["buy_equity"].iloc[0]


def test_very_high_rent_makes_buying_waste_less_within_horizon():
    params = {**DEFAULTS, "rent_monthly": 200_000}
    df = compute.rent_vs_buy(**params)
    last = df.iloc[-1]
    assert last["buy_wasted_cum"] < last["rent_wasted_cum"]


def test_very_low_rent_makes_renting_waste_less_within_horizon():
    params = {**DEFAULTS, "rent_monthly": 3_000}
    df = compute.rent_vs_buy(**params)
    last = df.iloc[-1]
    assert last["rent_wasted_cum"] < last["buy_wasted_cum"]


# Allocation-weighted return helper (used to default the calculator's invest_return).

def test_expected_return_for_target_weights_by_pct():
    target = {"mfs": 50, "gold_metals": 50}
    rate = compute.expected_return_for_target(target)
    assert rate == pytest.approx(0.5 * compute.EXPECTED_RETURNS["mfs"] + 0.5 * compute.EXPECTED_RETURNS["gold_metals"])


def test_renter_contributed_is_portfolio_minus_gain():
    """The non-investing renter's cash pile: portfolio = contributed + gain."""
    df = compute.rent_vs_buy(**DEFAULTS)
    row = df.iloc[5]
    assert row["renter_portfolio"] == pytest.approx(row["renter_contributed"] + row["renter_gain"])


def test_invest_discipline_haircuts_the_renters_growth():
    """Rv 2026-07-21: a renter rarely invests the whole EMI-vs-rent gap.
    Investing less of the difference must yield a smaller portfolio gain, while
    the rent actually paid (their baseline waste) is unchanged."""
    full = compute.rent_vs_buy(**DEFAULTS, invest_discipline_pct=100)
    lean = compute.rent_vs_buy(**DEFAULTS, invest_discipline_pct=80)
    assert lean.iloc[-1]["renter_gain"] < full.iloc[-1]["renter_gain"]
    assert lean.iloc[-1]["rent_wasted_cum"] == pytest.approx(full.iloc[-1]["rent_wasted_cum"])
    # So the renter's net gain (the chart's bar) drops with less-disciplined investing.
    assert lean.iloc[-1]["rent_wasted_net"] > full.iloc[-1]["rent_wasted_net"]


def test_invest_discipline_default_is_the_full_amount():
    """The compute default stays 100% — the haircut is opt-in from the view."""
    a = compute.rent_vs_buy(**DEFAULTS)
    b = compute.rent_vs_buy(**DEFAULTS, invest_discipline_pct=100)
    assert a.iloc[-1]["renter_gain"] == pytest.approx(b.iloc[-1]["renter_gain"])
