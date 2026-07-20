import pandas as pd, pytest, storage
from pathlib import Path


def test_save_raises_when_the_audit_record_cannot_be_written(tmp_path, monkeypatch):
    """Codex 2026-07-21: audit failures were swallowed, so a save could land
    on disk with no trail and the user would never know."""
    monkeypatch.setattr(storage, "log_change", lambda *a, **k: "OSError: disk full")
    df = pd.DataFrame([{"profile": "rv", "year": 2026, "month": 1, "salary": 100,
                        "bonus": 0, "other": 0, "job_change": 0}])
    with pytest.raises(storage.AuditLogError):
        storage.save_income(tmp_path, df)
    # The data must still be safely written — the audit is the only casualty.
    assert (tmp_path / "income.csv").exists()
    assert len(pd.read_csv(tmp_path / "income.csv")) == 1


def test_write_is_atomic_and_leaves_no_temp_file(tmp_path):
    df = pd.DataFrame([{"profile": "rv", "year": 2026, "month": 1, "salary": 100,
                        "bonus": 0, "other": 0, "job_change": 0}])
    storage.save_income(tmp_path, df)
    assert not list(tmp_path.glob(".*.tmp"))


# YAML guardrails (Codex 2026-07-21): a financial model shouldn't accept an
# allocation that only balances on paper, or a config that breaks every rate.

import pytest as _pytest
from pydantic import ValidationError

import models


def _profile(**over):
    base = dict(key="rv", name="Rv", birth_year=1998, forward_increment_pct=10,
                default_target={"mfs": 60, "gold_metals": 40})
    return models.Profile(**{**base, **over})


def test_allocation_rejects_negative_weights_even_when_it_sums_to_100():
    with _pytest.raises(ValidationError, match="negative"):
        _profile(default_target={"mfs": 120, "gold_metals": -20})


def test_allocation_rejects_empty_target():
    with _pytest.raises(ValidationError, match="at least one"):
        _profile(default_target={})


def test_config_rejects_empty_or_duplicated_categories():
    with _pytest.raises(ValidationError, match="empty"):
        models.Config(categories=[])
    with _pytest.raises(ValidationError, match="duplicates"):
        models.Config(categories=["mfs", "mfs"])


def test_config_rejects_an_implausible_return():
    with _pytest.raises(ValidationError, match="0-30"):
        models.Config(categories=["mfs"], expected_return_pct=95)
