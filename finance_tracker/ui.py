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


def is_dark() -> bool:
    """Follow Streamlit's native theme (☰ → Settings → Theme). Letting Streamlit
    own the theme is the only flicker-free way; our custom HTML just reads it."""
    try:
        return st.context.theme.type == "dark"
    except Exception:
        return False


def grid_color() -> str:
    return "#3a3f4b" if is_dark() else "#eef1f3"


# Colors for our custom HTML, chosen to sit on Streamlit's native light/dark
# surfaces. Streamlit themes its own widgets, tables and background natively.
_VARS = {
    False: ("--text:#1f1f1f;--muted:#7c828c;--card-bg:#ffffff;--card-border:#e7eaee;"
            "--strip-bg:#f3faf9;--strip-border:#d4e7e4;--strip-text:#0F766E;"),
    True: ("--text:#fafafa;--muted:#a3a8b4;--card-bg:#1b1f2b;--card-border:#363b48;"
           "--strip-bg:#10211f;--strip-border:#1f3d39;--strip-text:#5eead4;"),
}


def inject_theme() -> None:
    """Inter font + CSS variables that track Streamlit's native theme. No
    background/widget overrides (those caused the flicker); Streamlit owns those."""
    st.markdown(
        f"<style>"
        f"@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');"
        f":root{{{_VARS[is_dark()]}}}"
        f"html, body, .stApp, [class*='css'], button, input, textarea, select "
        f"{{font-family:'Inter',-apple-system,sans-serif !important;}}"
        f"h1,h2,h3{{letter-spacing:-0.01em;}}"
        f".ht{{border-collapse:collapse;width:100%;font-size:.84rem}}"
        f".ht th{{text-align:right;color:var(--muted);font-weight:600;padding:6px 10px;border-bottom:1px solid var(--card-border)}}"
        f".ht td{{text-align:right;padding:6px 10px;border-bottom:1px solid var(--card-border);color:var(--text)}}"
        f".ht th:first-child,.ht td:first-child{{text-align:left}}"
        f".ht tr.cur td{{background:var(--strip-bg);font-weight:600}}"
        f".ht tr.proj td{{color:var(--muted);font-style:italic}}"
        f"</style>",
        unsafe_allow_html=True,
    )


def html_table(df, headers: dict, formats: dict | None = None, row_class=None) -> None:
    """Render a read-only DataFrame as a themed HTML table that respects dark
    mode (st.dataframe is canvas-rendered and can't be themed by CSS)."""
    formats = formats or {}
    head = "".join(f"<th>{h}</th>" for h in headers.values())
    body = ""
    for _, r in df.iterrows():
        cls = row_class(r) if row_class else ""
        cells = "".join(f"<td>{formats.get(c, str)(r[c])}</td>" for c in headers)
        body += f"<tr class='{cls}'>{cells}</tr>"
    st.markdown(f"<table class='ht'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>",
                unsafe_allow_html=True)


def metric_tile(col, label_text: str, value: str, sub: str = "", color: str | None = None, big: bool = False) -> None:
    """A bordered dashboard tile: small uppercase label, bold value, muted sub.
    Themes via CSS variables; pass color only for an accent value (teal/mulberry)."""
    size = "1.9rem" if big else "1.35rem"
    value_color = color or "var(--text)"
    col.markdown(
        f"<div style='border:1px solid var(--card-border);border-radius:12px;padding:14px 16px;"
        f"background:var(--card-bg);height:100%'>"
        f"<div style='font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em'>{label_text}</div>"
        f"<div style='font-size:{size};font-weight:700;color:{value_color};margin-top:3px;line-height:1.1'>{value}</div>"
        f"<div style='font-size:.76rem;color:var(--muted);margin-top:3px'>{sub}</div></div>",
        unsafe_allow_html=True,
    )


def style_fig(fig, height: int = 320):
    """Clean, Power-BI-ish Plotly styling: Inter font, no chrome, soft grid."""
    dark = is_dark()
    text = "#cfd3da" if dark else INK
    fig.update_layout(
        font=dict(family="Inter, sans-serif", size=13, color=text),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=34, b=8), height=height,
        legend=dict(orientation="h", yanchor="bottom", y=1.04, x=0, title=None),
        hoverlabel=dict(font_family="Inter", bgcolor="#191d24" if dark else "white"),
        bargap=0.35,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, showline=False)
    fig.update_yaxes(showgrid=True, gridcolor=grid_color(), zeroline=False, showline=False)
    return fig


def page_header(title: str, profiles) -> list[str]:
    """Title, a top-right View multiselect, and a dark-mode toggle. Returns the
    selected profile keys (empty selection means everyone)."""
    inject_theme()
    left, right = st.columns([3, 1], vertical_alignment="bottom")
    left.title(title)
    names = [p.name for p in profiles]
    selected = right.multiselect("View", names, default=names, key="scope")
    keys = [p.key for p in profiles if p.name in selected]
    return keys or [p.key for p in profiles]
