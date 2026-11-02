"""Shared test setup."""

import pytest

import compute


@pytest.fixture(autouse=True)
def fixed_increment_splits(monkeypatch):
    """Pins the increment splits the hand-worked numbers in the tests assume,
    so retuning a person's split in config.py doesn't break them."""
    monkeypatch.setattr(compute, "PROFILE_INCREMENT_SPLITS", {
        "rv": {"needs": 25, "wants": 25, "investment": 50},
        "cheeni": {"needs": 30, "wants": 20, "investment": 50},
    })
