"""Central configuration for CBSE Finances.

Holds every tunable value in one place: the colour palette, the budget-model
constants, the income components, and the category labels. Other modules import
from here rather than hard-coding values.
"""

# Palette: a grayscale base plus two accents. Teal marks actuals and the current
# year; mulberry marks planned, projected, and target figures.
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

# Budget model. The anchor year (a person's first) splits income 50/30/20 across
# needs/wants/investment; every later year splits only the income *increment*
# 20/30/50, so raises flow mostly to investing.
BASE_SPLIT = {"needs": 50, "wants": 30, "investment": 20}
INCREMENT_SPLIT = {"needs": 20, "wants": 30, "investment": 50}
PROJECTION_YEARS_AHEAD = 3  # budget projects to the current year plus this many
ON_TRACK_PCT = 75  # a year is "on track" at or above this share of its goal

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
