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
COST_LINE = "#9aa0a6"  # the net-worth chart's cost-basis line
MARKER = "#64748b"  # slate chart markers (job-change triangle)
FONT = "Inter"

# Per-person accent pair: (primary = actuals/current, secondary = planned/
# projected). Profiles are told apart by colour, not a name. Picked to read on
# both light and dark backgrounds *and* to pass WCAG AA (≥4.5:1) as small text
# on white; the shared grays stay the neutral base.
#   rv     → platinum monochrome (graphite + steel)
#   cheeni → pink family (light pink + deep raspberry)
PROFILE_ACCENTS = {
    "rv": (GRAPHITE, STEEL),
    "cheeni": (PINK, RASPBERRY),
}
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
    "ppf_nps": 10.0,  # EPF / PPF / NPS blended
    "fixed_deposit": 7.0,
}
NETWORTH_PROJECTION_YEARS = 5  # how far the net-worth projection looks ahead
# An EMI is really funded out of wants + investment: needs are committed
# spending (an EMI can't come out of groceries), so a house is paid for by
# giving up discretionary spend and investing less. This is the share of that
# envelope a home loan may claim — the default the affordability slider opens at.
EMI_SHARE_OF_WANTS_INVESTMENT_PCT = 70

# A buyer is forced to "save" via the EMI; a renter with a smaller outgoing
# rarely invests the whole difference — some leaks into lifestyle. This is the
# share of that monthly gap the renter actually invests, in the rent-vs-buy
# comparison. Below 100 stops the renting side from looking unrealistically good.
RENTER_INVEST_DISCIPLINE_PCT = 80

# Emergency-fund *target* = this many months of the needs bucket (essential
# spending only; wants pause in an emergency). The target is derived; the
# *actual* fund held is entered by hand (see storage.ALLOWED_ADJUSTMENTS).
EMERGENCY_FUND_MONTHS = 4

# The components that sum to a year's total income. "other" catches anything
# beyond salary and bonus (RSU vesting, an FD/RD maturing, and so on).
INCOME_COMPONENTS = ["salary", "bonus", "other"]

# Display names for the asset-class categories used across the app.
CATEGORY_LABELS = {
    "us_market": "US market",
    "indian_stocks": "Indian stocks",
    "mfs": "Mutual funds",
    "fixed_deposit": "Fixed deposit",
    "ppf_nps": "EPF / PPF / NPS",
    "gold_metals": "Gold / metals",
}
