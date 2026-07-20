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


def test_net_columns_are_the_assets_directly():
    """Both sides spend the same housing budget, so assets compare directly —
    subtracting waste again would double-count (the renter's portfolio already
    paid the rent out of that budget; Codex review 2026-07-20)."""
    df = compute.rent_vs_buy(**DEFAULTS)
    row = df.iloc[5]
    assert row["buy_net"] == pytest.approx(row["buy_equity"])
    assert row["rent_net"] == pytest.approx(row["renter_portfolio"])


def test_crossover_year_found_when_rent_eventually_costlier():
    params = {**DEFAULTS, "rent_monthly": 60_000, "rent_inflation_pct": 8}
    df = compute.rent_vs_buy(**params)
    year = compute.rent_vs_buy_crossover_year(df)
    assert year is not None
    row = df[df["year"] == year].iloc[0]
    assert row["buy_wasted_cum"] <= row["rent_wasted_cum"]
    if year > 1:
        prev = df[df["year"] == year - 1].iloc[0]
        assert prev["buy_wasted_cum"] > prev["rent_wasted_cum"]


def test_crossover_year_none_when_renting_always_wastes_less():
    params = {**DEFAULTS, "rent_monthly": 1_000, "rent_inflation_pct": 0, "horizon_years": 5}
    df = compute.rent_vs_buy(**params)
    assert compute.rent_vs_buy_crossover_year(df) is None


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
