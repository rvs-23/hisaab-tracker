import pandas as pd
import streamlit as st

from finance_tracker import compute, storage
from finance_tracker.ui import inr, load_all

d = load_all()
keys = [p.key for p in d.profiles]
cats = d.config.categories

st.title("Update data")
st.caption(
    "Edit a table and Save. Everything is a plain file in the data folder — direct "
    "edits work too. The budget split is derived from income, so there's nothing to edit there."
)


def editor(df, column_config, validate, save, key, label, sort=None):
    data = df.sort_values(sort).reset_index(drop=True) if (sort and not df.empty) else df.reset_index(drop=True)
    edited = st.data_editor(
        data, num_rows="dynamic", hide_index=True, width="stretch",
        column_config=column_config, key=key,
    )
    if st.button(f"Save {label}", key=f"save_{key}"):
        try:
            validate(edited)
            save(d.root, edited)
            st.success(f"Saved {label}")
        except Exception as exc:
            st.error(f"Not saved: {exc}")


income_tab, target_tab, contrib_tab, goals_tab = st.tabs(
    ["Income", "Targets", "Contributions", "Goals"]
)

with income_tab:
    st.caption("Annual income per person. Salary + bonus + other drives the whole budget.")
    editor(
        d.income,
        {
            "profile": st.column_config.SelectboxColumn("Person", options=keys, required=True),
            "year": st.column_config.NumberColumn("Year", format="%d", required=True),
            "salary": st.column_config.NumberColumn("Salary (₹)", required=True),
            "bonus": st.column_config.NumberColumn("Bonus (₹)", required=True),
            "other": st.column_config.NumberColumn("Other (₹)", required=True),
        },
        lambda df: storage.validate_income(df, d.profiles),
        storage.save_income, "income_editor", "income", sort=["profile", "year"],
    )

with target_tab:
    st.caption(
        "You set the **%** per instrument (two tiers, each summing to 100). Rupee "
        "amounts auto-calculate from these × your budget — preview below. Years with "
        "no rows here fall back to the profile's default_target."
    )
    editor(
        d.targets,
        {
            "profile": st.column_config.SelectboxColumn("Person", options=keys, required=True),
            "year": st.column_config.NumberColumn("Year", format="%d", required=True),
            "tier": st.column_config.SelectboxColumn("Tier", options=["short_term", "long_term"], required=True),
            "category": st.column_config.SelectboxColumn("Category", options=cats, required=True),
            "pct": st.column_config.NumberColumn("Percent", required=True),
        },
        lambda df: storage.validate_targets(df, d.config, d.profiles),
        storage.save_targets, "targets_editor", "targets",
    )

    st.divider()
    st.markdown("**Auto-calculated planned amounts** (target % × budget pools)")
    years = compute.available_years(d.income, d.contributions)
    if years:
        c1, c2 = st.columns(2)
        person = c1.selectbox("Person", d.profiles, format_func=lambda p: p.name, key="prev_person")
        pyear = c2.selectbox("Year", years, index=len(years) - 1, key="prev_year")
        exp = compute.expected_contributions(person, d.income, d.targets, pyear)
        if exp:
            prev = pd.DataFrame({"category": exp.keys(), "planned": exp.values()}).sort_values(
                "planned", ascending=False
            )
            st.metric("Total planned investment", inr(prev["planned"].sum()))
            st.dataframe(
                prev,
                column_config={
                    "category": "Category",
                    "planned": st.column_config.NumberColumn("Planned (₹)", format="%.0f"),
                },
                hide_index=True, width="stretch",
            )

with contrib_tab:
    st.caption("What you actually invested, per person / year / category.")
    editor(
        d.contributions,
        {
            "year": st.column_config.NumberColumn("Year", format="%d", required=True),
            "profile": st.column_config.SelectboxColumn("Person", options=keys, required=True),
            "category": st.column_config.SelectboxColumn("Category", options=cats, required=True),
            "amount": st.column_config.NumberColumn("Amount (₹)", required=True),
            "notes": "Notes",
        },
        lambda df: storage.validate_contributions(df, d.config, d.profiles),
        storage.save_contributions, "contrib_editor", "contributions", sort=["year", "profile", "category"],
    )

with goals_tab:
    st.caption("Emergency-fund goal, per person / year.")
    editor(
        d.goals,
        {
            "year": st.column_config.NumberColumn("Year", format="%d", required=True),
            "profile": st.column_config.SelectboxColumn("Person", options=keys, required=True),
            "emergency_fund_goal": st.column_config.NumberColumn("Emergency-fund goal (₹)", required=True),
        },
        lambda df: storage.validate_goals(df, d.profiles),
        storage.save_goals, "goals_editor", "goals", sort=["year", "profile"],
    )
