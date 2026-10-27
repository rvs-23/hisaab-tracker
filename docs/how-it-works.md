# How this tracker works: a 5-minute guide

For anyone using the app for the first time (hi, Cheeni 👋). No finance or code
background needed. The technical details live in the [README](../README.md).

## The one idea

The app answers one question: **did we invest what the plan said this year?**
It doesn't track what your investments are *worth*: no live prices, no market
values. The plan said put in ₹X, you put in ₹Y.

Everything starts from your income:

```
Income  →  Budget  →  Allocation  →  Investments
(you type) (derived) (you set %s)   (you record)
```

- **Income** is the only money fact you enter. Everything else is computed
  from it or compared against it.
- **Budget** splits that income into needs / wants / investment. Your first
  earning year uses the base split. After that, only each year's *raise* is
  split, and that split leans toward investing, so the more you earn, the
  bigger the share you invest. The Budget page shows your exact percentages
  (they live in `config.py`). You never type a budget; changing income
  changes it.
- **Allocation** is how the investment slice spreads across instruments
  (mutual funds 45%, gold 25%, …). Percentages must sum to 100. A year's
  allocation carries forward until you set a newer one. It sits on the
  **Budget** page, under the monthly split, so you can see what each
  instrument takes out of the monthly goal.
- **Investments** is where you record what you invested. Do it whenever money
  goes in: open it, pick the year, add or update a row, Save. The plan sits
  next to it.

## Your page, your colours

The app shows **one person at a time**. Open it with your own link and keep it
bookmarked:

- `http://localhost:8501/?profile=rv`
- `http://localhost:8501/?profile=cheeni`
- `http://localhost:8501/?profile=household` (both of you, read-only)

There's no switch button and no name on the page. The **accent colours** tell
you whose page it is: platinum grays for rv, pink and raspberry for cheeni,
teal for the household. The choice sticks as you move between pages.

Under every page title, a small line says when data was last entered and on
which page, so you can tell at a glance whether Investments are up to date.

## Reading the Dashboard

Top to bottom:

1. **Four lifetime tiles:** earned to date, invested to date, what it could
   be worth today at conservative growth, and the year's **total goal** (this
   year's plan plus any shortfall carried over from past years).
2. **The journey, year on year:** bars show total income and the planned
   goal side by side, and a line shows what you actually invested.
3. **Allocation today:** everything you've contributed so far, split across
   instruments and stacked by the year each rupee went in (lightest is oldest).
4. **Catch up:** if past years fell short of the plan, this is the lump sum
   that, invested today, pulls you level. Zero means you're on plan. Investing
   *more* than planned is always fine.
5. **Health:** short nudges that appear only when something needs a look: no
   income entered yet this year, investing badly behind pace, no emergency
   fund recorded, or this year's mix drifting from target.
6. **Adjustments:** a small expander at the bottom for your **opening
   corpus**, the money you'd already invested before you started tracking
   (say, ₹20L before 2024). Set it once. It's assumed invested at the start of
   your first tracked year and grown at the household rate. It counts toward
   "Invested till date" and the estimated value. It stays out of the budget,
   the goal, catch-up and plan-vs-actual, which only cover what you've tracked.

On the household page, the tiles and charts add both of you together. Health
nudges and Adjustments stay on each person's own page.

Everywhere in the app, the **primary accent means "what actually happened"**
and the **secondary accent means "what was planned"**.

## House fund

Open it with `?profile=household`. It answers one question: **if we keep
investing like this, how much could we put down on a house at the end of each
year?**

Only money you can sell counts: stocks, mutual funds, US market, gold and FDs.
EPF / PPF / NPS is locked until retirement and the emergency fund stays put, so
both are left out. The opening corpus counts unless you untick it.

Each bar is the whole pot at the end of that year, in two parts: what you
already have, grown, and what you'll save from now on, grown. Change the
inputs and the chart redraws. Nothing is saved.

- **Return:** growth on everything (defaults to the household rate).
- **Invest per year:** defaults to this year's recorded liquid investments,
  scaled up to a full year. If Investments are behind, it reads low, so put in
  your real number.
- **Pace grows:** how much more you invest each year as income rises.
- **Years ahead:** how far out to look.

Registration and stamp duty aren't taken out; keep them aside from the number.

## What to do, and when

- **Monthly (2 minutes):** nothing is required, but recording contributions on
  **Investments** as you invest beats reconstructing them in December.
- **When salary changes** (raise, bonus, job switch): update that year on
  **Income**. Tick "Job change this year?" if you switched jobs. A tax payment
  or clawback goes under *other*, the one field allowed to go negative.
- **Once a year:** check the target allocation on **Budget** still matches
  where you want money to go.
- **Zerodha for equities/MFs?** `scripts/zerodha_summary.py` shows what went in
  from any tradebook export, and `scripts/import_tradebook.py` turns a year of
  it into one contribution row. The README has the commands.

## Things that surprise people

- **The emergency-fund *target* is automatic:** 3 months
  (`EMERGENCY_FUND_MONTHS`) of your current monthly salary, so it grows with
  your pay. What you *actually* hold is entered by hand on
  Investments and counts toward your estimated value.
- **Saving is safe.** Every save is checked first (sums, duplicates, blanks,
  negative numbers except income's *other*) and refused with a message if
  something's off. Every change is also appended to an audit log
  (`changes.jsonl`).
- **A year you earned nothing** has no budget, so it doesn't distort other
  years.
- **Catch-up covers past years only.** This year's remaining goal shows as
  "left to go". On the journey chart, the current year's goal bar covers only
  the part of the year that has passed.
- The ₹ figures use Indian grouping and short forms: `₹55.8L` is 55.8 lakh,
  `₹3.40Cr` is 3.40 crore.
