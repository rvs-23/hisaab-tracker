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

# House fund defaults. The years shown are fixed: two actual years for context,
# then the projection.
HOUSE_FUND_YEARS = (2024, 2034)
HOUSE_FUND_GROWTH_PCT = 5.0  # yearly growth of the monthly investment
# Retirement money is left out of the House fund corpus: provident funds and
# NPS can't be drawn for a down payment.
HOUSE_FUND_EXCLUDED = ["epf", "ppf", "nps"]
HOUSE_FUND_INFLATION_PCT = 7.0  # default for showing future rupees in today's money
# The realistic down payment leaves this share of the corpus invested, so buying
# the house doesn't empty every account (2026-11-02).
HOUSE_FUND_KEEP_PCT = 30.0
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
    "cheeni": {"needs": 30, "wants": 20, "investment": 50},
}
# A person whose increment split changes over time lists it by period: each
# period's first year maps to its split, which applies until the next period
# starts. Past periods stay locked, so a new split never rewrites past goals.
# Takes priority over PROFILE_INCREMENT_SPLITS.
PROFILE_INCREMENT_SPLIT_PERIODS = {
    # Locked from 2023 on 2026-11-02. Add a year here when a new split starts.
    "rv": {2023: {"needs": 25, "wants": 30, "investment": 45}},
}
PROJECTION_YEARS_AHEAD = 3  # budget projects to the current year plus this many
ON_TRACK_PCT = 75  # a year is "on track" at or above this share of its goal

# The earliest year any selector offers: tracking starts in 2023.
BASELINE_YEAR = 2023

# Emergency-fund *target* = budgeted needs + investment over this many months,
# the latest ones up to today (2026-11-02). The *actual* fund held is entered by
# hand (see storage.ALLOWED_ADJUSTMENTS).
EMERGENCY_FUND_MONTHS = 4

# The components that sum to a year's total income. "other" catches anything
# beyond salary and bonus (RSU vesting, an FD/RD maturing, and so on).
INCOME_COMPONENTS = ["salary", "bonus", "other"]

# Display names for the asset-class categories used across the app.
CATEGORY_LABELS = {
    "us_market": "US market",
    "indian_stocks": "Indian stocks",
    "mfs": "Mutual funds (equity)",
    "fixed_deposit": "Fixed deposit",
    "epf": "EPF",
    "ppf": "PPF",
    "nps": "NPS",
    "aif": "AIF",
    "gold_metals": "Gold",
    "debt_funds": "Mutual funds (arbitrage / debt)",
}

# Mutual funds that hold safe money rather than shares (2026-11-02). The
# tradebook importer files these under debt_funds instead of mfs.
DEBT_FUND = (r"\b(?:ARBITRAGE|LIQUID|OVERNIGHT|MONEY MARKET|ULTRA SHORT|SHORT DURATION|"
             r"LOW DURATION|CORPORATE BOND|BANKING (?:AND|&) PSU|GILT|DYNAMIC BOND)\b")
