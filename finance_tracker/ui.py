"""Streamlit-side helpers shared by all views."""

from __future__ import annotations

import streamlit as st

from finance_tracker import storage


class Data:
    """Everything loaded fresh from disk for one page render (no caching —
    every view re-reads, so edits show up on the next refresh)."""

    def __init__(self, root, config, profiles, income, targets, contributions, goals):
        self.root = root
        self.config = config
        self.profiles = profiles
        self.income = income
        self.targets = targets
        self.contributions = contributions
        self.goals = goals


def load_all() -> "Data":
    try:
        root = storage.data_dir()
        config = storage.load_config(root)
        profiles = storage.load_profiles(root, config)
        income = storage.load_income(root, profiles)
        targets = storage.load_targets(root, config, profiles)
        contributions = storage.load_contributions(root, config, profiles)
        goals = storage.load_goals(root, profiles)
    except Exception as exc:
        st.error(f"Could not load data: {exc}")
        st.stop()
    return Data(root, config, profiles, income, targets, contributions, goals)


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


def inr_short(n: float) -> str:
    """Compact ₹ for metric cards — lakh/crore so big numbers fit at 100% zoom.
    ₹55,76,912 → ₹55.8L ; ₹3,40,00,000 → ₹3.40Cr ; small values stay grouped."""
    n = round(n)
    a = abs(n)
    sign = "-" if n < 0 else ""
    if a >= 1_00_00_000:
        return f"{sign}₹{a / 1_00_00_000:.2f}Cr"
    if a >= 1_00_000:
        return f"{sign}₹{a / 1_00_000:.1f}L"
    return inr(n)


# Visual language (design.md): grayscale base + exactly two accents.
# Teal marks what happened (actuals, the current year); mulberry marks what's
# intended (planned, projected, targets). No traffic-light semantics.
TEAL = "#0F766E"
MULBERRY = "#86198F"
INK = "#2b2b2b"

# Grayscale ramp for charts — dark first (household / primary series).
GRAYS = ["#2b2b2b", "#7a7a7a", "#a8a8a8", "#c9c9c9", "#e0e0e0"]


def grays(n: int) -> list[str]:
    """n monochrome shades, darkest first."""
    return GRAYS[:n] if n <= len(GRAYS) else GRAYS + GRAYS[: n - len(GRAYS)]


def page_header(title: str, profiles) -> list[str]:
    """Render the page title with a top-right multi-select View. Shared widget
    key, so the choice sticks across navigation. Returns the selected profile
    keys (empty selection is treated as everyone). When 2+ are selected, pages
    also show a combined total."""
    left, right = st.columns([3, 1], vertical_alignment="bottom")
    left.title(title)
    names = [p.name for p in profiles]
    selected = right.multiselect("View", names, default=names, key="scope")
    keys = [p.key for p in profiles if p.name in selected]
    return keys or [p.key for p in profiles]
