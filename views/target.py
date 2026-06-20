import datetime as dt

import pandas as pd
import streamlit as st

from finance_tracker import compute, storage
from finance_tracker.ui import html_table, inr, inr_short, load_all, page_header, pretty_category

d = load_all()
scope = page_header("Target", d.profiles)
st.caption(
    "Where investment money should go, in %. Two tiers: **long-term** for investment "
    "money, **short-term** for the slice of wants money you invest. A year's rows "
    "carry forward until you add newer ones; with none, the profile's default applies."
)

CURRENT_YEAR = dt.date.today().year

# What's in force right now, with auto-calculated ₹ — per selected person.
for profile in (p for p in d.profiles if p.key in scope):
    target = compute.resolve_target(profile, d.targets, CURRENT_YEAR)
    expected = compute.expected_contributions(profile, d.income, d.targets, CURRENT_YEAR)
    st.subheader(f"{profile.name} — in force for {CURRENT_YEAR}")
    if not expected:
        st.info(f"No income entered for {profile.name} yet — add it on the Income page.")
        continue
    rows = []
    for tier, label in (("long_term", "Long-term"), ("short_term", "Short-term")):
        for cat, pct in sorted(target[tier].items(), key=lambda kv: -kv[1]):
            rows.append({"tier": label, "category": cat, "pct": pct})
    in_force = pd.DataFrame(rows)
    in_force["yearly"] = [expected.get(r.category, 0.0) for r in in_force.itertuples()]
    html_table(
        in_force,
        {"tier": "Tier", "category": "Category", "pct": "Target %", "yearly": "≈ This year"},
        formats={
            "category": pretty_category,
            "pct": lambda v: f"{v:.0f}%",
            "yearly": inr_short,
        },
    )
    st.caption(f"Total planned this year: {inr(sum(expected.values()))}")

st.divider()
st.subheader("Edit per-year targets")
st.caption("Each (person, year, tier) must sum to 100. Rupee amounts above recalculate automatically.")
edited = st.data_editor(
    d.targets.sort_values(["profile", "year", "tier", "category"]).reset_index(drop=True)
    if not d.targets.empty else d.targets,
    num_rows="dynamic", hide_index=True, width="stretch", key="targets_editor",
    column_config={
        "profile": st.column_config.SelectboxColumn("Person", options=[p.key for p in d.profiles], required=True),
        "year": st.column_config.NumberColumn("Year", format="%d", required=True),
        "tier": st.column_config.SelectboxColumn("Tier", options=["short_term", "long_term"], required=True),
        "category": st.column_config.SelectboxColumn("Category", options=d.config.categories, required=True),
        "pct": st.column_config.NumberColumn("Target %", required=True),
    },
)
if st.button("Save targets", type="primary"):
    try:
        storage.validate_targets(edited, d.config, d.profiles)
        storage.save_targets(d.root, edited)
        st.success("Saved.")
        st.rerun()
    except Exception as exc:
        st.error(f"Not saved: {exc}")
