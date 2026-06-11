"""Streamlit-side helpers shared by all views."""

from __future__ import annotations

import streamlit as st

from finance_tracker import storage


def load_all():
    """Fresh read of every data file, called at the top of each view — the
    spec requires recomputing from current files on every load, so nothing
    here is cached."""
    try:
        root = storage.data_dir()
        config = storage.load_config(root)
        profiles = storage.load_profiles(root)
        holdings = storage.load_holdings(root, config, profiles)
        income = storage.load_income(root, profiles)
    except Exception as exc:
        st.error(f"Could not load data: {exc}")
        st.stop()
    return root, config, profiles, holdings, income


def inr(n: float) -> str:
    """₹ with Indian digit grouping: 1234567 -> ₹12,34,567."""
    n = round(n)
    sign = "-" if n < 0 else ""
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while head:
            groups.insert(0, head[-2:])
            head = head[:-2]
        s = ",".join(groups + [tail])
    return f"{sign}₹{s}"


def scope_picker(profiles, label: str = "Scope") -> str | None:
    """Household / per-person selector. Returns a profile key or None for household."""
    options = {"Household (combined)": None} | {p.name: p.key for p in profiles}
    choice = st.selectbox(label, list(options))
    return options[choice]
