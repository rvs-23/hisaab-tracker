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


# Grayscale ramp for charts — dark first (household / primary series).
GRAYS = ["#2b2b2b", "#7a7a7a", "#a8a8a8", "#c9c9c9", "#e0e0e0"]


def grays(n: int) -> list[str]:
    """n monochrome shades, darkest first."""
    return GRAYS[:n] if n <= len(GRAYS) else GRAYS + GRAYS[: n - len(GRAYS)]


def edit_grid(df, column_config, validate, save, root, key, label, sort=None) -> None:
    """A collapsed 'Edit …' expander holding an editable grid + Save button.
    Edits the whole underlying file; validates before writing so a bad edit is
    rejected with a message rather than corrupting the data."""
    data = df.sort_values(sort).reset_index(drop=True) if sort else df.reset_index(drop=True)
    with st.expander(f"✎ Edit {label}"):
        edited = st.data_editor(
            data, num_rows="dynamic", hide_index=True, width="stretch",
            column_config=column_config, key=key,
        )
        if st.button(f"Save {label}", key=f"save_{key}"):
            try:
                validate(edited)
                save(root, edited)
                st.success(f"Saved {label}")
            except Exception as exc:
                st.error(f"Not saved: {exc}")


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
