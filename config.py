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
TEAL = "#0F766E"
MULBERRY = "#86198F"
MUTED = "#7c828c"
CARD_BG = "#ffffff"
CARD_BORDER = "#e7eaee"
GRID = "#eef1f3"
STRIP_BG = "#f3faf9"
STRIP_BORDER = "#d4e7e4"
STRIP_TEXT = TEAL
SAND = "#dfe4e8"  # neutral income bar
NEEDS = "#b9c0c7"  # the "needs" slice of the budget split
FONT = "Inter"

# Per-person accent pair: (primary = actuals/current, secondary = planned/
# projected). Profiles are told apart by colour, not a name. Picked to read on
# both light and dark backgrounds; the shared grays stay the neutral base.
#   rv     → teal + mulberry
#   cheeni → pink + indigo
PROFILE_ACCENTS = {
    "rv": (TEAL, MULBERRY),
    "cheeni": ("#DB2777", "#6366F1"),
}
DEFAULT_ACCENTS = (TEAL, MULBERRY)

# Budget model. The anchor year (a person's first) splits income 50/30/20 across
# needs/wants/investment; every later year splits only the income *increment*
# 20/30/50, so raises flow mostly to investing.
BASE_SPLIT = {"needs": 50, "wants": 30, "investment": 20}
INCREMENT_SPLIT = {"needs": 20, "wants": 30, "investment": 50}
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
    "ppf_nps": 8.0, "bonds_gsec_aif": 7.5, "fixed_deposit": 7.0,
}
NETWORTH_PROJECTION_YEARS = 5  # how far the net-worth projection looks ahead

# Emergency fund = this many months of the needs bucket (6 months of essential
# spending). Derived from income like the rest of the budget — never entered.
EMERGENCY_FUND_MONTHS = 6

# The components that sum to a year's total income. "other" catches anything
# beyond salary and bonus (RSU vesting, an FD/RD maturing, and so on).
INCOME_COMPONENTS = ["salary", "bonus", "other"]

# Display names for the asset-class categories used across the app.
CATEGORY_LABELS = {
    "us_market": "US market",
    "indian_stocks": "Indian stocks",
    "mfs": "Mutual funds",
    "fixed_deposit": "Fixed deposit",
    "ppf_nps": "PPF / NPS",
    "bonds_gsec_aif": "Bonds / Gsec / AIF",
    "gold_metals": "Gold / metals",
}
