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


def test_max_loan_for_emi_is_the_exact_inverse_of_emi():
    for principal, rate, tenure in [(5_000_000, 8.5, 20), (12_000_000, 9.25, 15),
                                    (2_500_000, 7.0, 30)]:
        monthly = compute.emi(principal, rate, tenure)
        assert compute.max_loan_for_emi(monthly, rate, tenure) == pytest.approx(principal, rel=1e-9)


def test_max_loan_for_emi_zero_rate_is_flat_multiplication():
    assert compute.max_loan_for_emi(50_000, 0, 20) == pytest.approx(50_000 * 240)


def test_sip_for_target_future_value_hits_the_target():
    """The SIP inverse must round-trip through the standard FV formula."""
    target, rate, years = 10_000_000, 11.5, 10
    sip = compute.sip_for_target(target, rate, years)
    r, n = rate / 1200, years * 12
    assert sip * ((1 + r) ** n - 1) / r == pytest.approx(target, rel=1e-9)


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


# best_buy_year — timing the purchase.

TIMING = dict(
    price=15_000_000, down_pct=20, loan_rate_pct=8.5, tenure_years=20,
    registration_pct=7, maintenance_pct=0.5, appreciation_pct=5,
    rent_monthly=40_000, rent_inflation_pct=5, invest_return_pct=11.5,
    horizon_years=15, starting_corpus=5_000_000, monthly_saving=150_000,
)


def test_best_buy_year_covers_the_horizon_inclusively():
    """A 15-year horizon must offer buying now through waiting all fifteen —
    16 options, not 15 (the label says years of waiting)."""
    df = compute.best_buy_year(**TIMING)
    assert list(df["wait_years"]) == list(range(TIMING["horizon_years"] + 1))


def test_waiting_grows_the_corpus_and_shrinks_the_loan():
    """The whole reason waiting can win: savings compound into a bigger down
    payment, so the loan falls even though the house costs more."""
    df = compute.best_buy_year(**TIMING)
    assert df["price_then"].is_monotonic_increasing
    assert df["corpus"].is_monotonic_increasing
    assert df["loan"].is_monotonic_decreasing
    assert df.iloc[-1]["loan"] == 0.0  # eventually bought outright


def test_savings_create_an_interior_optimum():
    """With real monthly saving the cheapest year is neither the first nor the
    last — waiting pays until appreciation and rent outrun the corpus."""
    df = compute.best_buy_year(**TIMING)
    best = int(df[df["feasible"]]["total_wasted"].idxmin())
    assert 0 < best < TIMING["horizon_years"]


def test_without_savings_buying_now_wins():
    """No monthly saving means waiting buys nothing but rent and a pricier
    house, so the optimum collapses to year 0."""
    # The corpus must clear registration + the minimum down payment today, or
    # year 0 is simply unaffordable and the earliest feasible year wins by default.
    df = compute.best_buy_year(**{**TIMING, "monthly_saving": 0, "starting_corpus": 6_000_000})
    assert bool(df.iloc[0]["feasible"])
    assert int(df[df["feasible"]]["total_wasted"].idxmin()) == 0


def test_interest_is_charged_over_the_full_tenure_not_the_horizon():
    """Guards the bias that made waiting look free: buying late must still be
    charged for every rupee of its loan."""
    df = compute.best_buy_year(**{**TIMING, "starting_corpus": 0, "monthly_saving": 0})
    late = df.iloc[-1]
    monthly = compute.emi(late["loan"], TIMING["loan_rate_pct"], TIMING["tenure_years"])
    full_interest = monthly * TIMING["tenure_years"] * 12 - late["loan"]
    assert late["interest_paid"] == pytest.approx(full_interest, rel=1e-6)


def test_a_small_corpus_marks_early_years_infeasible():
    df = compute.best_buy_year(**{**TIMING, "starting_corpus": 500_000, "monthly_saving": 50_000})
    assert not bool(df.iloc[0]["feasible"])
    assert bool(df.iloc[-1]["feasible"])


def test_emi_budget_gates_feasibility_not_just_cash():
    """Codex 2026-07-21: cash alone approved years whose EMI the household
    could never service. A tiny budget must make even cash-rich years unusable."""
    # Cash-rich enough to clear registration + the down payment, but still
    # borrowing — a corpus that buys outright would owe no EMI at all.
    rich = {**TIMING, "starting_corpus": 6_000_000, "monthly_saving": 0}
    assert compute.best_buy_year(**rich, emi_budget=500_000)["feasible"].any()
    tight = compute.best_buy_year(**rich, emi_budget=1_000)
    early = tight[tight["wait_years"] < 5]
    assert early["cash_ok"].any()          # the cash is there
    assert not early["emi_ok"].any()       # but the EMI never fits
    assert not early["feasible"].any()     # so the year is not affordable


def test_zero_emi_budget_skips_the_serviceability_test():
    """0 means 'no budget known' — fall back to the cash test rather than
    silently marking every year unaffordable."""
    df = compute.best_buy_year(**TIMING, emi_budget=0)
    assert (df["feasible"] == df["cash_ok"]).all()


def test_inflation_discounts_future_costs():
    """Same nominal scenario, discounted: waste must come out lower, and more
    so for later purchases whose costs sit further out."""
    nominal = compute.best_buy_year(**TIMING, inflation_pct=0)
    real = compute.best_buy_year(**TIMING, inflation_pct=6)
    assert (real["total_wasted"] < nominal["total_wasted"]).all()
    shrink = 1 - real["total_wasted"] / nominal["total_wasted"]
    assert shrink.iloc[-1] > shrink.iloc[0]


def test_maintenance_grows_with_inflation():
    flat = compute.best_buy_year(**TIMING, inflation_pct=0).iloc[0]["maintenance_paid"]
    base = TIMING["price"] * TIMING["maintenance_pct"] / 100
    assert flat == pytest.approx(base * TIMING["tenure_years"])


def test_starting_corpus_changes_the_recommendation():
    """Codex 2026-07-21: the toggle test only checked a caption string. Prove
    the model itself moves when the corpus is excluded."""
    with_corpus = compute.best_buy_year(**TIMING)
    without = compute.best_buy_year(**{**TIMING, "starting_corpus": 0})
    assert (without["corpus"] < with_corpus["corpus"]).all()
    assert (without["loan"] >= with_corpus["loan"]).all()
    best_with = int(with_corpus[with_corpus["feasible"]]["total_wasted"].idxmin())
    best_without = int(without[without["feasible"]]["total_wasted"].idxmin())
    assert best_without > best_with  # no head start means waiting longer
