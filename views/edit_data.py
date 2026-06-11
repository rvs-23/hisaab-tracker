import streamlit as st

from finance_tracker import storage
from finance_tracker.ui import load_all

d = load_all()
profile_keys = [p.key for p in d.profiles]

st.title("Update data")
st.caption(
    "Everything is a plain file — editing the CSVs/YAMLs directly in "
    f"`{d.root}` works just as well as this page."
)

budget_tab, contrib_tab, goals_tab, income_tab = st.tabs(
    ["Budget", "Contributions", "Goals", "Income"]
)


def save_grid(edited, validate, save, label):
    if st.button(f"Save {label}", key=f"save_{label}"):
        try:
            validate(edited)
            save(d.root, edited)
            st.success(f"Saved {label}")
        except Exception as exc:
            st.error(f"Not saved: {exc}")


with budget_tab:
    st.caption("Monthly needs + wants + investment must equal gross salary ÷ 12.")
    edited = st.data_editor(
        d.budget.sort_values(["profile", "year"]).reset_index(drop=True),
        num_rows="dynamic", hide_index=True, width="stretch", key="budget_editor",
        column_config={
            "profile": st.column_config.SelectboxColumn("Person", options=profile_keys, required=True),
            "year": st.column_config.NumberColumn("Year", format="%d", required=True),
            "starting_salary": st.column_config.NumberColumn("Starting salary (₹)"),
            "job_change": st.column_config.SelectboxColumn("Job change?", options=["No", "Yes"]),
            "ending_salary": st.column_config.NumberColumn("Gross salary (₹)", required=True),
            "monthly_needs": st.column_config.NumberColumn("Needs /mo (₹)", required=True),
            "monthly_wants": st.column_config.NumberColumn("Wants /mo (₹)", required=True),
            "monthly_investment": st.column_config.NumberColumn("Invest /mo (₹)", required=True),
        },
    )
    save_grid(edited, lambda df: storage.validate_budget(df, d.profiles), storage.save_budget, "budget")

with contrib_tab:
    st.caption("What you actually invested, per person / year / category.")
    edited = st.data_editor(
        d.contributions.sort_values(["year", "profile", "category"]).reset_index(drop=True),
        num_rows="dynamic", hide_index=True, width="stretch", key="contrib_editor",
        column_config={
            "year": st.column_config.NumberColumn("Year", format="%d", required=True),
            "profile": st.column_config.SelectboxColumn("Person", options=profile_keys, required=True),
            "category": st.column_config.SelectboxColumn("Category", options=d.config.categories, required=True),
            "amount": st.column_config.NumberColumn("Amount (₹)", required=True),
            "notes": "Notes",
        },
    )
    save_grid(
        edited,
        lambda df: storage.validate_contributions(df, d.config, d.profiles),
        storage.save_contributions,
        "contributions",
    )

with goals_tab:
    st.caption("Emergency-fund goal, per person / year.")
    edited = st.data_editor(
        d.goals.sort_values(["year", "profile"]).reset_index(drop=True),
        num_rows="dynamic", hide_index=True, width="stretch", key="goals_editor",
        column_config={
            "year": st.column_config.NumberColumn("Year", format="%d", required=True),
            "profile": st.column_config.SelectboxColumn("Person", options=profile_keys, required=True),
            "emergency_fund_goal": st.column_config.NumberColumn("Emergency-fund goal (₹)", required=True),
        },
    )
    save_grid(edited, lambda df: storage.validate_goals(df, d.profiles), storage.save_goals, "goals")

with income_tab:
    st.caption("Non-salary income (bonus / other).")
    edited = st.data_editor(
        d.income.sort_values("date", ascending=False).reset_index(drop=True),
        num_rows="dynamic", hide_index=True, width="stretch", key="income_editor",
        column_config={
            "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD", required=True),
            "profile": st.column_config.SelectboxColumn("Person", options=profile_keys, required=True),
            "source": st.column_config.TextColumn("Source", required=True),
            "amount": st.column_config.NumberColumn("Amount (₹)", required=True),
            "notes": "Notes",
        },
    )
    save_grid(edited, lambda df: storage.validate_income(df, d.profiles), storage.save_income, "income")
