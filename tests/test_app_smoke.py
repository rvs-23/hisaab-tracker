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
    "views/allocation.py",
    "views/actuals.py",
]

TARGET = (
    "default_target: {mfs: 45, gold_metals: 25, indian_stocks: 14, us_market: 10, ppf_nps: 5, bonds_gsec_aif: 1}\n"
)


@pytest.fixture
def fake_data_dir(tmp_path, monkeypatch):
    (tmp_path / "config.yaml").write_text(
        "usd_inr_rate: 84.0\n"
        "usd_inr_as_of: 2026-06-01\n"
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
        "usd_inr_rate: 84.0\n"
        "usd_inr_as_of: 2026-06-01\n"
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
def test_page_renders_without_errors(page, fake_data_dir):
    at = AppTest.from_file(str(REPO_ROOT / page), default_timeout=20).run()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_on_fresh_data_dir(page, fresh_data_dir):
    """README promises config.yaml + profiles/ is enough to start — no CSVs."""
    at = AppTest.from_file(str(REPO_ROOT / page), default_timeout=20).run()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]
