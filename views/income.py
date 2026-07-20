import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import compute
import storage
from config import INCOME_COMPONENTS as COMPONENTS
from ui import (
    CHART_TEXT, MARKER, accent_primary, accent_secondary, edit_card, inr_axis,
    inr_short, load_all, page_header, resync, section, style_fig,
)

d = load_all()
active = page_header("Income", d.profiles)
PRIMARY, SECONDARY = accent_primary(), accent_secondary()  # per-person colours

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
ss = st.session_state

# Income over time, on top.
visible = d.income[d.income["profile"] == active.key]
if not visible.empty:
    section("Income over time")
    totals = visible.assign(total=visible[COMPONENTS].sum(axis=1)).groupby("year")["total"].sum()
    yr = totals.index.astype(int).astype(str)
    f = go.Figure()
    f.add_bar(x=yr, y=totals, name="Income", marker_color=PRIMARY)
    # YoY income growth above each bar, so the raise is visible at a glance.
    growth = ["" if pd.isna(v) else f"+{v:.0f}%" for v in totals.pct_change() * 100]
    f.add_trace(go.Scatter(
        x=yr, y=totals, mode="text", text=growth, textposition="top center",
        textfont=dict(size=11, color=CHART_TEXT), showlegend=False, hoverinfo="skip",
        cliponaxis=False))
    # Mark job-change years with a marker above the bar.
    jc = visible.groupby("year")["job_change"].max()
    jc_years = [int(y) for y in jc.index if jc.loc[y] > 0]
    if jc_years:
        f.add_trace(go.Scatter(
            x=[str(y) for y in jc_years], y=[totals[y] for y in jc_years],
            mode="markers", name="Job change",
            marker=dict(symbol="triangle-down", size=10, color=MARKER, line=dict(width=1, color="white")),
            hovertext="Job change", hoverinfo="text+x"))
    f.update_layout(xaxis=dict(type="category"))
    inr_axis(f, totals.max())
    style_fig(f, height=280)
    st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

section("Enter income")
st.caption("Pick a year and fill the 12 months. Salary, bonus, and anything else (RSU vesting, an FD or RD maturing) under Other.")

this_year = dt.date.today().year
year_options = compute.selectable_years(d.income, d.contributions, active.key)
default_year = this_year if this_year in year_options else year_options[-1]
c1, _ = st.columns([1, 3])
year = int(c1.selectbox("Year", year_options, index=year_options.index(default_year)))


def annual(yr):
    rows = d.income[(d.income["profile"] == active.key) & (d.income["year"] == yr)]
    return rows[COMPONENTS].sum().sum()


def saved_job_change(yr):
    rows = d.income[(d.income["profile"] == active.key) & (d.income["year"] == yr)]
    return bool(rows["job_change"].max()) if not rows.empty else False


def disk_rows(yr):
    return d.income[(d.income["profile"] == active.key) & (d.income["year"] == yr)]


def rows_sig(rows):
    """An order-independent fingerprint of a year's income rows, for detecting
    whether the on-disk data changed (or whether a save would be a no-op)."""
    cols = ["month", *COMPONENTS, "job_change"]
    if rows.empty:
        return ()
    return tuple(sorted(
        tuple(int(round(float(v))) for v in r) for r in rows[cols].to_numpy()
    ))


def fresh_grid(yr):
    grid = pd.DataFrame({"Month": MONTHS})
    for component in COMPONENTS:
        grid[component] = 0
    mine = d.income[(d.income["profile"] == active.key) & (d.income["year"] == yr)]
    prev = d.income[(d.income["profile"] == active.key) & (d.income["year"] == yr - 1)]
    if not mine.empty:
        for _, r in mine.iterrows():
            grid.loc[int(r["month"]) - 1, COMPONENTS] = [r[c] for c in COMPONENTS]
    elif not prev.empty and prev["salary"].sum():
        # New year: carry only last year's salary — a bonus or one-off "other"
        # isn't a recurring monthly amount.
        grid["salary"] = round(prev["salary"].sum() / 12)
    grid["Total"] = grid[COMPONENTS].sum(axis=1)
    return grid


with edit_card(f"Enter {year}"):
    base = f"inc_{active.key}_{year}"
    gkey, vkey, skey = f"{base}_grid", f"{base}_ver", f"{base}_seed"
    if gkey not in ss:
        ss[gkey] = fresh_grid(year)
        ss[vkey] = 0
        ss[skey] = rows_sig(disk_rows(year))  # what disk held when this grid opened

    edited = st.data_editor(
        ss[gkey], num_rows="fixed", hide_index=True, width="stretch",
        key=f"{base}_{ss[vkey]}",
        column_config={
            "Month": st.column_config.TextColumn("Month", disabled=True),
            "salary": st.column_config.NumberColumn("Salary (₹)", required=True, format="localized"),
            "bonus": st.column_config.NumberColumn("Bonus (₹)", required=True, format="localized"),
            "other": st.column_config.NumberColumn("Other (₹)", required=True, format="localized"),
            "Total": st.column_config.NumberColumn("Total (₹)", disabled=True, format="localized"),
        },
    )
    # Recompute the (disabled) Total live as the user types.
    resync(gkey, vkey, edited.assign(Total=edited[COMPONENTS].sum(axis=1)), ["Total"])

    job_change = st.checkbox("Job change this year?", value=saved_job_change(year),
                             key=f"{base}_jc")
    filled = int((edited[COMPONENTS].sum(axis=1) > 0).sum())
    total = edited[COMPONENTS].sum().sum()
    prev_total = annual(year - 1)
    delta = f"{100 * (total - prev_total) / prev_total:+.0f}% vs {year - 1}" if prev_total else "first year"

    # Does the grid (only its *committed* cells) differ from what's on disk? This
    # is the honest signal: if you typed a value but the cell hasn't committed
    # yet, it isn't here, and this reads "in sync" — telling you the edit hasn't
    # registered before you hit Save.
    preview = edited[COMPONENTS].assign(month=range(1, 13), job_change=int(job_change))
    pending = rows_sig(preview) != rows_sig(disk_rows(year))
    if pending:
        st.markdown(f"<div style='color:{PRIMARY};font-weight:600;font-size:.82rem'>"
                    "● Unsaved changes — press Enter to commit the cell, then Save.</div>",
                    unsafe_allow_html=True)
    else:
        st.markdown("<div style='color:var(--muted);font-size:.82rem'>"
                    "✓ In sync with saved data — nothing to save.</div>",
                    unsafe_allow_html=True)

    b2, b3 = st.columns([1, 3])
    if b2.button("Save", key=f"{base}_save", type="primary"):
        current = rows_sig(disk_rows(year))
        new = edited[COMPONENTS].copy()
        new["profile"], new["year"], new["month"] = active.key, year, range(1, 13)
        new["job_change"] = int(job_change)
        new = new[storage.INCOME_COLUMNS]
        if ss.get(skey) is not None and ss[skey] != current:
            # Disk moved under this grid (another tab, or an import) — reload
            # rather than overwrite the newer data with our stale grid.
            st.warning(f"{year}'s income changed on disk since you opened this. Reloaded — "
                       "re-enter your change so nothing is overwritten.")
            ss.pop(gkey, None)
            ss.pop(skey, None)
            st.rerun()
        elif rows_sig(new) == current:
            # Nothing to write. Most often the last-typed cell never committed:
            # Streamlit's editor only captures a cell once it loses focus.
            st.toast("Nothing saved — your last edit hasn't committed.", icon="⚠️")
            st.warning("**No changes to save.** If you just typed a value, press **Enter** "
                       "(or click another cell) to commit it — the number turns from an "
                       "editing box into plain text — then Save. Nothing was written.")
        else:
            others = d.income[~((d.income["profile"] == active.key) & (d.income["year"] == year))]
            merged = pd.concat([others, new], ignore_index=True)
            try:
                storage.validate_income(merged, d.profiles)
                storage.save_income(d.root, merged)
                ss.pop(gkey, None)
                ss.pop(skey, None)
                st.success(f"Saved — {inr_short(total)} across {filled} month{'s' if filled != 1 else ''} of {year}.")
                st.rerun()
            except Exception as exc:
                st.error(f"Not saved: {exc}")
    b3.markdown(
        f"<div style='padding-top:.4rem;color:var(--muted)'>{filled} of 12 months entered &nbsp;·&nbsp; "
        f"<b style='color:var(--text)'>{inr_short(total)}</b> for {year} ({delta})</div>",
        unsafe_allow_html=True,
    )
