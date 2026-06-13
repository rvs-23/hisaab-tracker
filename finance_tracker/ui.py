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


CATEGORY_LABELS = {
    "us_market": "US market", "indian_stocks": "Indian stocks", "mfs": "Mutual funds",
    "fixed_deposit": "Fixed deposit", "ppf_nps": "PPF / NPS",
    "bonds_gsec_aif": "Bonds / Gsec / AIF", "gold_metals": "Gold / metals",
}


def pretty_category(c: str) -> str:
    return CATEGORY_LABELS.get(c, c.replace("_", " ").capitalize())


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


def inject_theme() -> None:
    """Load Inter (the modern-dashboard typeface) and a few polish tweaks. Runs
    once per page via page_header."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        html, body, .stApp, [class*="css"], button, input, textarea, select,
        [data-testid="stMetricValue"], [data-testid="stDataFrame"] {
            font-family: 'Inter', -apple-system, sans-serif !important;
        }
        h1, h2, h3 { letter-spacing: -0.01em; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def metric_tile(col, label_text: str, value: str, sub: str = "", color: str = INK, big: bool = False) -> None:
    """A bordered dashboard tile: small uppercase label, bold value, gray sub."""
    size = "1.9rem" if big else "1.35rem"
    col.markdown(
        f"<div style='border:1px solid #eceff1;border-radius:12px;padding:14px 16px;"
        f"background:#fff;height:100%'>"
        f"<div style='font-size:.7rem;color:#8a8a8a;text-transform:uppercase;letter-spacing:.05em'>{label_text}</div>"
        f"<div style='font-size:{size};font-weight:700;color:{color};margin-top:3px;line-height:1.1'>{value}</div>"
        f"<div style='font-size:.76rem;color:#8a8a8a;margin-top:3px'>{sub}</div></div>",
        unsafe_allow_html=True,
    )


def style_fig(fig, height: int = 320):
    """Clean, Power-BI-ish Plotly styling: Inter font, no chrome, soft grid."""
    fig.update_layout(
        font=dict(family="Inter, sans-serif", size=13, color=INK),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=46, b=8), height=height,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None),
        hoverlabel=dict(font_family="Inter", bgcolor="white"),
        title=dict(font=dict(size=14, color="#5a5a5a"), x=0, xanchor="left", y=0.97),
        bargap=0.35,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, showline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#eef1f3", zeroline=False, showline=False)
    return fig


def page_header(title: str, profiles) -> list[str]:
    inject_theme()
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
