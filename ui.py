"""Streamlit presentation helpers: data loading, formatting, and styling.

Colours and labels come from ``config``; this module re-exports the names that
views use so a view imports everything it needs from one place.
"""

from __future__ import annotations

from contextlib import contextmanager

import pandas as pd
import streamlit as st

import storage
from config import (  # re-exported for views
    CARD_BG, CARD_BORDER, CATEGORY_LABELS, GRID, INK, MULBERRY, MUTED,
    NEEDS, ON_TRACK_PCT, SAND, STRIP_BORDER, STRIP_BG, STRIP_TEXT, TEAL,
)


class Data:
    """A snapshot of every data file for one page render.

    Nothing is cached: each view re-reads from disk, so edits show up on the
    next refresh.
    """

    def __init__(self, root, config, profiles, income, targets, contributions):
        self.root = root
        self.config = config
        self.profiles = profiles
        self.income = income
        self.targets = targets
        self.contributions = contributions


def load_all() -> Data:
    """Loads and validates the whole data folder, or stops the page on error.

    Returns:
        A populated ``Data`` instance.
    """
    try:
        root = storage.data_dir()
        config = storage.load_config(root)
        profiles = storage.load_profiles(root, config)
        income = storage.load_income(root, profiles)
        targets = storage.load_targets(root, config, profiles)
        contributions = storage.load_contributions(root, config, profiles)
    except Exception as exc:
        st.error(f"Could not load data: {exc}")
        st.stop()
    return Data(root, config, profiles, income, targets, contributions)


# --- formatting ------------------------------------------------------------

def inr(value: float) -> str:
    """Formats rupees with Indian digit grouping, e.g. ``₹12,34,567``."""
    value = round(value)
    sign = "-" if value < 0 else ""
    digits = str(abs(value))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while head:
            groups.insert(0, head[-2:])
            head = head[:-2]
        digits = ",".join(groups + [tail])
    return f"{sign}₹{digits}"


def inr_short(value: float) -> str:
    """Formats rupees compactly for metric cards, e.g. ``₹55.8L`` or ``₹3.40Cr``."""
    value = round(value)
    magnitude = abs(value)
    sign = "-" if value < 0 else ""
    if magnitude >= 1_00_00_000:
        return f"{sign}₹{magnitude / 1_00_00_000:.2f}Cr"
    if magnitude >= 1_00_000:
        return f"{sign}₹{magnitude / 1_00_000:.1f}L"
    return inr(value)


def pretty_category(category: str) -> str:
    """Returns the display label for an asset-class category key."""
    return CATEGORY_LABELS.get(category, category.replace("_", " ").capitalize())


def grid_color() -> str:
    """Returns the chart gridline colour."""
    return GRID


# --- styling ---------------------------------------------------------------

_ROOT_VARS = (
    f"--text:{INK};--muted:{MUTED};--card-bg:{CARD_BG};--card-border:{CARD_BORDER};"
    f"--strip-bg:{STRIP_BG};--strip-border:{STRIP_BORDER};--strip-text:{STRIP_TEXT};"
)


def inject_theme() -> None:
    """Loads the Inter font and defines the CSS variables our custom HTML uses."""
    st.markdown(
        f"<style>"
        f"@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');"
        f":root{{{_ROOT_VARS}}}"
        f"html, body, .stApp, [class*='css'], button, input, textarea, select "
        f"{{font-family:'Inter',-apple-system,sans-serif !important;}}"
        f"h1,h2,h3{{letter-spacing:-0.01em;}}"
        f".ht{{border-collapse:collapse;width:100%;font-size:.84rem}}"
        f".ht th{{text-align:right;color:var(--muted);font-weight:600;padding:6px 10px;border-bottom:1px solid var(--card-border)}}"
        f".ht td{{text-align:right;padding:6px 10px;border-bottom:1px solid var(--card-border);color:var(--text)}}"
        f".ht th:first-child,.ht td:first-child{{text-align:left}}"
        f".ht tr.cur td{{background:var(--strip-bg);font-weight:600}}"
        f".ht tr.proj td{{color:var(--muted);font-style:italic}}"
        # slimmer sidebar
        f"section[data-testid='stSidebar']{{width:212px!important;min-width:212px!important}}"
        # bigger brand: st.logo caps the height; let it grow (stacked logo fits the slim rail)
        f"[data-testid='stLogo'],[data-testid='stSidebarLogo']{{height:3rem!important;width:auto!important}}"
        f"</style>",
        unsafe_allow_html=True,
    )


def metric_tile(col, label: str, value: str, sub: str = "", color: str | None = None,
                big: bool = False, help: str = "") -> None:
    """Renders a bordered KPI tile (uppercase label, bold value, muted sub).

    Args:
        col: The Streamlit container to render into.
        label: Small uppercase caption above the value.
        value: The headline figure.
        sub: Muted supporting line below the value.
        color: Value colour; defaults to the body text colour. Pass an accent
            (teal/mulberry) to highlight.
        big: Use the larger value size for hero tiles.
        help: Plain-language explanation shown as an (i) hover tooltip.
    """
    size = "1.9rem" if big else "1.35rem"
    info = (f" <span title='{help}' style='cursor:help;font-weight:400;"
            f"font-size:.85em'>&#9432;</span>") if help else ""
    col.markdown(
        f"<div style='border:1px solid var(--card-border);border-radius:12px;padding:14px 16px;"
        f"background:var(--card-bg);height:100%'>"
        f"<div style='font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em'>{label}{info}</div>"
        f"<div style='font-size:{size};font-weight:700;color:{color or 'var(--text)'};margin-top:3px;line-height:1.1'>{value}</div>"
        f"<div style='font-size:.76rem;color:var(--muted);margin-top:3px'>{sub}</div></div>",
        unsafe_allow_html=True,
    )


def html_table(df: pd.DataFrame, headers: dict, formats: dict | None = None,
               row_class=None) -> None:
    """Renders a read-only DataFrame as a styled HTML table.

    Args:
        df: Rows to render.
        headers: Maps column name to display header; only these columns show.
        formats: Optional map of column name to a value-formatting function.
        row_class: Optional callable mapping a row to a CSS class
            (``"cur"`` highlights, ``"proj"`` mutes).
    """
    formats = formats or {}
    head = "".join(f"<th>{h}</th>" for h in headers.values())
    body = ""
    for _, row in df.iterrows():
        cls = row_class(row) if row_class else ""
        cells = "".join(f"<td>{formats.get(c, str)(row[c])}</td>" for c in headers)
        body += f"<tr class='{cls}'>{cells}</tr>"
    st.markdown(f"<table class='ht'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>",
                unsafe_allow_html=True)


def style_fig(fig, height: int = 320):
    """Applies the shared Plotly look (Inter font, transparent bg, soft grid)."""
    fig.update_layout(
        font=dict(family="Inter, sans-serif", size=13, color=INK),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=34, b=8), height=height,
        legend=dict(orientation="h", yanchor="bottom", y=1.04, x=0),
        hoverlabel=dict(font_family="Inter", bgcolor="white"),
        bargap=0.35,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, showline=False)
    fig.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=False, showline=False)
    return fig


def section(label: str) -> None:
    """Renders a small uppercase section label to give a page rhythm."""
    st.markdown(
        f"<div style='color:var(--muted);font-size:.74rem;text-transform:uppercase;"
        f"letter-spacing:.06em;font-weight:600;margin:.9rem 0 .2rem'>{label}</div>",
        unsafe_allow_html=True,
    )


def resync(grid_key: str, version_key: str, recomputed, derived_cols: list[str]) -> None:
    """Keeps a data_editor's disabled/derived columns live.

    A disabled column shows the value from the editor's data argument, which lags
    a user's edit by one rerun. Call this right after the editor with the grid
    whose derived columns you've recomputed from the edits; if any changed, it
    stores the new grid and bumps the widget key so the editor re-renders with
    the fresh values immediately.

    Args:
        grid_key: Session key holding the editor's data grid.
        version_key: Session key holding the editor's version (suffix its key).
        recomputed: The edited grid with derived columns recomputed.
        derived_cols: Columns to compare to detect a change.
    """
    if grid_key in st.session_state and any(
        list(recomputed[c]) != list(st.session_state[grid_key][c]) for c in derived_cols
    ):
        st.session_state[grid_key] = recomputed
        st.session_state[version_key] += 1
        st.rerun()
    st.session_state[grid_key] = recomputed


@contextmanager
def edit_card(title: str):
    """A bordered card with a teal heading that marks an editable 'fill here' zone.

    Use as a context manager; everything in the body renders inside the card::

        with edit_card("Record contributions"):
            edited = st.data_editor(...)
            st.button("Save", ...)
    """
    with st.container(border=True):
        st.markdown(
            f"<div style='font-weight:700;color:{TEAL};font-size:.95rem;margin-bottom:.4rem'>"
            f"{title}</div>",
            unsafe_allow_html=True,
        )
        yield


def page_header(title: str, profiles):
    """Renders the page title and resolves the active person from the URL.

    Routing is per person via the ``?profile=<key>`` query param: one active
    profile at a time, so each page renders a single person's data (no overlay).
    There's deliberately **no on-page switcher** — you pick a person by setting
    the URL once (e.g. ``?profile=cheeni``) and it sticks across pages via session
    state, so the whole app follows your choice. Defaults to the alphabetically-
    first name (Brownie). The active name shows as a small, muted subtitle.

    Returns:
        The active Profile.
    """
    inject_theme()
    keys = [p.key for p in profiles]
    default = min(profiles, key=lambda p: p.name).key

    if st.query_params.get("profile") in keys:
        active = st.query_params["profile"]
    else:
        active = st.session_state.get("active_profile", default)
    if active not in keys:
        active = default
    st.session_state["active_profile"] = active
    st.query_params["profile"] = active  # keep the URL shareable/bookmarkable

    profile = next(p for p in profiles if p.key == active)
    st.title(title)
    st.markdown(
        f"<div style='margin:-.6rem 0 .8rem;color:{TEAL};font-weight:600;font-size:.95rem'>{profile.name}</div>",
        unsafe_allow_html=True,
    )
    return profile
