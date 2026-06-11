import datetime as dt

import pandas as pd
import streamlit as st

from finance_tracker import compute, storage
from finance_tracker.ui import load_all

root, config, profiles, holdings, income = load_all()

st.title("Update data")
st.caption(
    "Everything is a plain file — editing the CSVs/YAMLs directly in "
    f"`{root}` works just as well as this page."
)

holdings_tab, income_tab = st.tabs(["Holdings", "Income"])

with holdings_tab:
    with st.expander("Start a new snapshot (copies latest values, dated today)"):
        st.write(
            "Appends a copy of the selected person's most recent holdings with "
            "today's date — then edit the new rows' values below and save."
        )
        person = st.selectbox("Person", profiles, format_func=lambda p: p.name, key="snap_person")
        if st.button("Create snapshot rows"):
            latest = compute.current_holdings(holdings)
            new = latest[latest["profile"] == person.key].copy()
            if new.empty:
                st.warning(f"No existing rows for {person.name} to copy.")
            else:
                new["date"] = pd.Timestamp(dt.date.today())
                storage.save_holdings(root, pd.concat([holdings, new], ignore_index=True))
                st.rerun()

    edited = st.data_editor(
        holdings.sort_values(["date", "profile", "category"], ascending=[False, True, True]),
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        column_config={
            "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD", required=True),
            "profile": st.column_config.SelectboxColumn(
                "Person", options=[p.key for p in profiles], required=True
            ),
            "instrument": st.column_config.TextColumn("Instrument", required=True),
            "category": st.column_config.SelectboxColumn(
                "Category", options=config.categories, required=True
            ),
            "currency": st.column_config.SelectboxColumn(
                "Currency", options=sorted(storage.CURRENCIES), required=True
            ),
            "value": st.column_config.NumberColumn("Value", required=True),
            "notes": "Notes",
        },
        key="holdings_editor",
    )
    if st.button("Save holdings"):
        try:
            df = edited.copy()
            df["date"] = pd.to_datetime(df["date"])
            storage.validate_holdings(df, config, profiles)
            storage.save_holdings(root, df)
            st.success("Saved holdings.csv")
        except Exception as exc:
            st.error(f"Not saved: {exc}")

with income_tab:
    edited_income = st.data_editor(
        income.sort_values("date", ascending=False),
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        column_config={
            "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD", required=True),
            "profile": st.column_config.SelectboxColumn(
                "Person", options=[p.key for p in profiles], required=True
            ),
            "source": st.column_config.TextColumn("Source", required=True),
            "amount": st.column_config.NumberColumn("Amount (₹)", required=True),
            "notes": "Notes",
        },
        key="income_editor",
    )
    if st.button("Save income"):
        try:
            df = edited_income.copy()
            df["date"] = pd.to_datetime(df["date"])
            storage.validate_income(df, profiles)
            storage.save_income(root, df)
            st.success("Saved income.csv")
        except Exception as exc:
            st.error(f"Not saved: {exc}")
