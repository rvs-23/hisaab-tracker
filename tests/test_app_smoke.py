"""Render every page headlessly against a throwaway data folder."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from finance_tracker import storage

REPO_ROOT = Path(__file__).resolve().parent.parent

PAGES = [
    "views/dashboard.py",
    "views/allocation.py",
    "views/plan_vs_actual.py",
    "views/budget_projection.py",
    "views/income.py",
    "views/edit_data.py",
]


@pytest.fixture
def fake_data_dir(tmp_path, monkeypatch):
    (tmp_path / "config.yaml").write_text(
        "usd_inr_rate: 80.0\n"
        "usd_inr_as_of: 2026-06-01\n"
        "categories: [zerodha_equity, ppf]\n"
        "target_mix: {zerodha_equity: 60, ppf: 40}\n"
    )
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "rv.yaml").write_text(
        "name: Rv\nbirth_year: 1995\nmonthly_salary: 100000\n"
        "salary_increment_pct: 8\n"
        "split: {needs: 50, wants: 20, investment: 30}\n"
        "projection_start_year: 2026\nprojection_years: 5\n"
    )
    (tmp_path / "holdings.csv").write_text(
        "date,profile,instrument,category,currency,value,notes\n"
        "2026-05-01,rv,Zerodha,zerodha_equity,INR,100000,\n"
        "2026-06-01,rv,Zerodha,zerodha_equity,INR,110000,\n"
        "2026-06-01,rv,PPF,ppf,INR,50000,\n"
    )
    (tmp_path / "income.csv").write_text(
        "date,profile,source,amount,notes\n2026-05-31,rv,salary,100000,\n"
    )
    monkeypatch.setattr(storage, "data_dir", lambda: tmp_path)
    return tmp_path


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_errors(page, fake_data_dir):
    at = AppTest.from_file(str(REPO_ROOT / page), default_timeout=15).run()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]
