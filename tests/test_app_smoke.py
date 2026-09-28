"""Render every page headlessly against a throwaway data folder."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import storage

REPO_ROOT = Path(__file__).resolve().parent.parent

PAGES = [
    "views/dashboard.py",
    "views/income.py",
    "views/budget_projection.py",
    "views/actuals.py",
    "views/rent_vs_buy.py",
]

TARGET = (
    "default_target: {mfs: 45, gold_metals: 25, indian_stocks: 5, us_market: 10, ppf_nps: 5, fixed_deposit: 10}\n"
)


@pytest.fixture
def fake_data_dir(tmp_path, monkeypatch):
    (tmp_path / "config.yaml").write_text(
        "categories: [us_market, indian_stocks, mfs, fixed_deposit, ppf_nps, gold_metals]\n"
    )
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "rv.yaml").write_text(
        "name: Rv\nbirth_year: 1998\nforward_increment_pct: 10\n" + TARGET
    )
    (profiles / "cheeni.yaml").write_text(
        "name: Cheeni\nbirth_year: 1998\nforward_increment_pct: 10\n" + TARGET
    )
    (tmp_path / "income.csv").write_text(
        "profile,year,month,salary,bonus,other,job_change\n"
        "rv,2023,1,1107389,0,0,0\n"
        "rv,2024,1,1425283,0,0,0\n"
        "rv,2025,1,3571045,0,0,1\n"
    )
    (tmp_path / "contributions.csv").write_text(
        "year,profile,category,amount,notes\n"
        "2024,rv,us_market,39345.5,\n"
        "2024,rv,mfs,169766,\n"
    )
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def fresh_data_dir(tmp_path, monkeypatch):
    """A brand-new folder: only config.yaml + profiles/, no history CSVs yet."""
    (tmp_path / "config.yaml").write_text(
        "categories: [us_market, indian_stocks, mfs, fixed_deposit, ppf_nps, gold_metals]\n"
    )
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "rv.yaml").write_text(
        "name: Rv\nbirth_year: 1998\nforward_increment_pct: 10\n" + TARGET
    )
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    return tmp_path


@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("profile", ["rv", "cheeni"])
def test_page_renders_without_errors(page, profile, fake_data_dir):
    """Render every page for BOTH profiles — the default profile is the one
    without data in this fixture, so rendering only it would skip every chart
    branch (this blind spot once hid an undefined-name crash)."""
    at = AppTest.from_file(str(REPO_ROOT / page), default_timeout=20)
    at.query_params["profile"] = profile
    at.run()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_on_fresh_data_dir(page, fresh_data_dir):
    """README promises config.yaml + profiles/ is enough to start — no CSVs."""
    at = AppTest.from_file(str(REPO_ROOT / page), default_timeout=20).run()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]


# Rent vs buy is now a single net-cost chart (no budget/timing sections) — it
# reads none of the person's own data, so it renders the same for both profiles.

def test_rent_vs_buy_states_the_net_cost_verdict(fake_data_dir):
    at = AppTest.from_file(str(REPO_ROOT / "views/rent_vs_buy.py"), default_timeout=20)
    at.query_params["profile"] = "rv"
    at.run()
    assert not at.exception, at.exception
    captions = " ".join(c.value for c in at.caption)
    assert "comes out ahead by" in captions    # the verdict
    assert "net gain" in captions.lower()       # framed as net gain
    assert "the two asset piles" in captions    # the equity-vs-gain table caption


def test_income_noop_save_warns_instead_of_confirming(fake_data_dir):
    """Saving without a real change must say so, not flash a misleading 'Saved.'
    — this is the cell-didn't-commit symptom that looked like a lost edit. The
    first save fills the 12 months; a second, unchanged save is the no-op."""
    at = AppTest.from_file(str(REPO_ROOT / "views/income.py"), default_timeout=20)
    at.query_params["profile"] = "rv"
    at.run()
    at.selectbox[0].set_value(2023).run()  # rv 2023 has one seeded month
    at.button(key="inc_rv_2023_save").click().run()   # writes all 12 months
    at.button(key="inc_rv_2023_save").click().run()   # nothing changed now
    assert not at.exception, at.exception
    assert "No changes to save" in " ".join(m.value for m in at.warning)
    assert "Saved" not in " ".join(s.value for s in at.success)


def test_rent_vs_buy_per_year_view_switches_the_chart(fake_data_dir):
    """The Cumulative/Per year toggle must recompute without error."""
    at = AppTest.from_file(str(REPO_ROOT / "views/rent_vs_buy.py"), default_timeout=20)
    at.query_params["profile"] = "rv"
    at.run()
    at.radio(key="rvb_view_rv").set_value("Per year").run()
    assert not at.exception, at.exception



def test_rent_vs_buy_explains_a_buying_win_as_a_buying_win(fake_data_dir):
    """The 'it wins because' clause once always credited investing — even when
    buying won. Strong appreciation vs a weak return must read as buying's win."""
    at = AppTest.from_file(str(REPO_ROOT / "views/rent_vs_buy.py"), default_timeout=20)
    at.query_params["profile"] = "rv"
    at.run()
    at.number_input(key="rvb_appr_rv").set_value(12.0)
    at.number_input(key="rvb_return_rv").set_value(4.0).run()
    assert not at.exception, at.exception
    captions = " ".join(c.value for c in at.caption)
    assert "buying comes out ahead" in captions
    assert "investing outpaces" not in captions


def test_flash_shows_on_the_next_run_then_clears(fake_data_dir):
    """Saves queue their confirmation (ui.flash) instead of calling st.success
    right before st.rerun, which the browser wipes. page_header shows a queued
    message once. (AppTest keeps stale elements a browser clears, so the old
    bug itself can't be reproduced here — this pins the mechanism instead.)"""
    at = AppTest.from_file(str(REPO_ROOT / "views/actuals.py"), default_timeout=20)
    at.query_params["profile"] = "rv"
    at.session_state["_flash"] = ("success", "Saved.")
    at.run()
    assert "Saved." in " ".join(s.value for s in at.success)
    assert "_flash" not in at.session_state


def test_save_queues_its_confirmation(fake_data_dir):
    at = AppTest.from_file(str(REPO_ROOT / "views/actuals.py"), default_timeout=20)
    at.query_params["profile"] = "rv"
    at.run()
    at.number_input(key="ef_rv").set_value(150_000)
    at.button(key="save_ef_rv").click().run()
    assert not at.exception, at.exception
    assert "Saved." in " ".join(s.value for s in at.success)
    assert "emergency_fund,150000" in (fake_data_dir / "adjustments.csv").read_text()


def test_audit_failure_reads_as_saved_but_unaudited(fake_data_dir, monkeypatch):
    """The CSV is written before the audit record; if only the audit fails the
    page must not claim 'Not saved'."""
    monkeypatch.setattr(storage, "log_change", lambda *a, **k: "OSError: disk full")
    at = AppTest.from_file(str(REPO_ROOT / "views/actuals.py"), default_timeout=20)
    at.query_params["profile"] = "rv"
    at.run()
    at.number_input(key="ef_rv").set_value(150_000)
    at.button(key="save_ef_rv").click().run()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]
    assert "Saved, but the audit log" in " ".join(w.value for w in at.warning)
    assert "emergency_fund" in (fake_data_dir / "adjustments.csv").read_text()
