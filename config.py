"""Central configuration for the Personal Finances Tracker.

Holds every tunable value in one place: the colour palette, the budget-model
constants, the income components, and the category labels. Other modules import
from here rather than hard-coding values.
"""

# Palette: a grayscale base plus two accents. The accent *roles* are fixed —
# primary = actuals / current year, secondary = planned / projected / target —
# but the actual hues are per person, so the colour scheme alone tells whose data
# you're looking at (no name label needed). See PROFILE_ACCENTS below.
INK = "#2b2b2b"
GRAPHITE = "#334155"  # rv primary — dark gunmetal (the "platinum" scheme)
STEEL = "#64748B"  # rv secondary — lighter steel, so planned recedes
PINK = "#EC4899"  # cheeni primary — light bright pink (chart + large-text AA; small text is borderline ~3.5:1)
RASPBERRY = "#9D174D"  # cheeni secondary — deep raspberry, same pink family (not violet)
TEAL = "#0F766E"  # household primary — deep teal (≈5.5:1 on white)
DEEP_TEAL = "#134E4A"  # household secondary — darker teal, same family
MUTED = "#697077"  # ≈5:1 on white — the old #7c828c failed WCAG AA at small sizes
CARD_BG = "#ffffff"
CARD_BORDER = "#e7eaee"
GRID = "#eef1f3"
STRIP_BG = "#f4f6f8"  # current-year row highlight — neutral (was teal-tinted)
STRIP_BORDER = "#dde2e8"
STRIP_TEXT = GRAPHITE
SAND = "#dfe4e8"  # neutral income bar
NEEDS = "#b9c0c7"  # the "needs" slice of the budget split
CHART_TEXT = "#6b7280"  # muted grey for in-chart labels (YoY growth etc.)
MARKER = "#64748b"  # slate chart markers (job-change triangle)
FONT = "Inter"

# Per-person accent pair: (primary = actuals/current, secondary = planned/
# projected). Profiles are told apart by colour, not a name. Picked to read on
# both light and dark backgrounds *and* to pass WCAG AA (≥4.5:1) as small text
# on white; the shared grays stay the neutral base.
#   rv     → platinum monochrome (graphite + steel)
#   cheeni → pink family (light pink + deep raspberry)
#   household → teal family (both people combined, ?profile=household)
PROFILE_ACCENTS = {
    "rv": (GRAPHITE, STEEL),
    "cheeni": (PINK, RASPBERRY),
    "household": (TEAL, DEEP_TEAL),
}

# The combined view of everyone. Not a profiles/*.yaml file: it is derived
# from all the people, so it never appears in any CSV's profile column.
HOUSEHOLD_KEY = "household"

# Categories you can sell to fund a down payment. EPF/PPF/NPS is locked until
# retirement and the emergency fund stays put, so neither counts.
LIQUID_CATEGORIES = ["us_market", "indian_stocks", "mfs", "fixed_deposit", "gold_metals"]
HOUSE_FUND_YEARS_AHEAD = 10  # the House fund page's default horizon
DEFAULT_ACCENTS = (GRAPHITE, STEEL)

# Budget model. The anchor year (first earning year) splits income 50/30/20
# needs/wants/investment (2026-07-25 — the shared anchor for both people). Every
# later year splits only the income *increment* per the increment split below,
# so most of each raise flows to investing while the anchor buckets carry
# forward. UI text derives from these dicts — never hard-code them in a caption.
DEFAULT_BASE_SPLIT = {"needs": 50, "wants": 30, "investment": 20}
DEFAULT_INCREMENT_SPLIT = {"needs": 30, "wants": 20, "investment": 50}
# Both people share the 50/30/20 anchor (no base override). Increment stays
# per-person, unchanged.
PROFILE_BASE_SPLITS = {}
PROFILE_INCREMENT_SPLITS = {
    "rv": {"needs": 25, "wants": 25, "investment": 50},
    "cheeni": {"needs": 30, "wants": 20, "investment": 50},
}
PROJECTION_YEARS_AHEAD = 3  # budget projects to the current year plus this many
ON_TRACK_PCT = 75  # a year is "on track" at or above this share of its goal

# The earliest year any selector offers: a locked zero baseline. Real tracking
# starts 2023, so 2022 sits below it as an empty floor.
BASELINE_YEAR = 2022

# Conservative expected annual returns per category, for the net-worth
# projection (base estimates + 0.5%). Tune here. The emergency fund is treated
# as held cash (no growth).
EXPECTED_RETURNS = {
    "indian_stocks": 11.5, "mfs": 11.5, "us_market": 9.5, "gold_metals": 7.5,
    "epf": 8.25, "ppf": 7.1, "nps": 10.0,  # EPF and PPF at their declared rates
    "aif": 12.0,
    "fixed_deposit": 7.0,
}
NETWORTH_PROJECTION_YEARS = 5  # how far the net-worth projection looks ahead

# Emergency-fund *target* = this many months of current monthly salary
# (2026-10-27). The *actual* fund held is entered by hand (see
# storage.ALLOWED_ADJUSTMENTS).
EMERGENCY_FUND_MONTHS = 3

# The components that sum to a year's total income. "other" catches anything
# beyond salary and bonus (RSU vesting, an FD/RD maturing, and so on).
INCOME_COMPONENTS = ["salary", "bonus", "other"]

# Display names for the asset-class categories used across the app.
CATEGORY_LABELS = {
    "us_market": "US market",
    "indian_stocks": "Indian stocks",
    "mfs": "Mutual funds",
    "fixed_deposit": "Fixed deposit",
    "epf": "EPF",
    "ppf": "PPF",
    "nps": "NPS",
    "aif": "AIF",
    "gold_metals": "Gold",
}
