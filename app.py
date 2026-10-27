from pathlib import Path

import streamlit as st

from config import HOUSEHOLD_KEY
from ui import active_profile_key, inject_theme

st.set_page_config(page_title="Personal Finances Tracker", page_icon=":material/savings:", layout="wide")
st.logo(str(Path(__file__).parent / "logo.svg"), size="large")
inject_theme()  # Inter font + the CSS variables our HTML uses (light theme only)

household = active_profile_key() == HOUSEHOLD_KEY
# Every page is always registered, so switching profile in the URL on any page
# never hits "Page not found"; the ones that don't apply are just hidden. The
# household only reads (income, budget and investments are edited per person),
# and House fund is about both people.
shown = lambda for_household: "visible" if for_household == household else "hidden"
# Nav reads as the money pipeline: in -> split (allocation is edited on Budget,
# under the monthly split) -> record investments.
st.navigation([
    st.Page("views/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
    st.Page("views/income.py", title="Income", icon=":material/payments:", visibility=shown(False)),
    st.Page("views/budget_projection.py", title="Budget", icon=":material/call_split:",
            visibility=shown(False)),
    st.Page("views/investments.py", title="Investments", icon=":material/savings:",
            visibility=shown(False)),
    st.Page("views/house_fund.py", title="House fund", icon=":material/home:", visibility=shown(True)),
]).run()
