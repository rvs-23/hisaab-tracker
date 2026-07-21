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
    "default_target: {mfs: 45, gold_metals: 25, indian_stocks: 14, us_market: 10, ppf_nps: 5, bonds_gsec_aif: 1}\n"
)


@pytest.fixture
def fake_data_dir(tmp_path, monkeypatch):
    (tmp_path / "config.yaml").write_text(
        "categories: [us_market, indian_stocks, mfs, fixed_deposit, ppf_nps, bonds_gsec_aif, gold_metals]\n"
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
        "categories: [us_market, indian_stocks, mfs, fixed_deposit, ppf_nps, bonds_gsec_aif, gold_metals]\n"
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


# Rent vs buy's affordability section reads the person's own budget — rv has
# income in fake_data_dir, cheeni doesn't, so one profile exercises the
# needs+wants envelope and the other exercises its "no data yet" fallback.

def test_rent_vs_buy_verdict_names_the_leaner_side(fake_data_dir):
    at = AppTest.from_file(str(REPO_ROOT / "views/rent_vs_buy.py"), default_timeout=20)
    at.query_params["profile"] = "rv"
    at.run()
    assert not at.exception, at.exception
    captions = " ".join(c.value for c in at.caption)
    assert "wastes" in captions and "less" in captions
    assert "sit idle" in captions
    assert "Interest is front-loaded" in captions  # the amortization table's caption
    assert "of your wants + investment" in captions  # the affordability verdict


def test_rent_vs_buy_affordability_silent_without_data(fake_data_dir):
    at = AppTest.from_file(str(REPO_ROOT / "views/rent_vs_buy.py"), default_timeout=20)
    at.query_params["profile"] = "cheeni"  # no income in this fixture
    at.run()
    assert not at.exception, at.exception
    captions = " ".join(c.value for c in at.caption)
    assert "Add this year's income to see what your budget can carry" in captions


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


def test_rent_vs_buy_timing_compares_against_an_affordable_year(fake_data_dir):
    """When the corpus can't fund a purchase today, the verdict must say so
    rather than claim a later year is 'cheaper than buying today' — that
    comparison is against something the person cannot do (and read as a
    negative saving)."""
    at = AppTest.from_file(str(REPO_ROOT / "views/rent_vs_buy.py"), default_timeout=20)
    at.query_params["profile"] = "rv"
    at.run()
    assert not at.exception, at.exception
    captions = " ".join(c.value for c in at.caption)
    assert "You can't buy this house yet" in captions
    # The baseline it compares against must be a year the corpus can fund —
    # never "buying today" when today is out of reach.
    assert "buying today" not in captions


def test_rent_vs_buy_starting_corpus_can_be_excluded(fake_data_dir):
    """Unchecking 'use my current savings' must actually zero the corpus the
    timing model starts from, not just grey the input out."""
    at = AppTest.from_file(str(REPO_ROOT / "views/rent_vs_buy.py"), default_timeout=20)
    at.query_params["profile"] = "rv"
    at.run()
    before = " ".join(c.value for c in at.caption)
    at.checkbox(key="rvb_usecorpus_rv").uncheck().run()
    assert not at.exception, at.exception
    after = " ".join(c.value for c in at.caption)
    assert "= ₹0" in after
    assert before != after

