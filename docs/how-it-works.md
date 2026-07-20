# How this tracker works — a 5-minute guide

For anyone using the app for the first time (hi, Cheeni 👋). No finance or code
background needed. The technical details live in the [README](../README.md).

## The one idea

The app answers a single question: **did we invest what the plan said this
year?** It does not track what your investments are *worth* — no live prices,
no market values. Just: the plan said put in ₹X, you put in ₹Y.

Everything flows from one number — your income:

```
Income  →  Budget  →  Allocation  →  Actuals
(you type) (derived) (you set %s)   (you record)
```

- **Income** is the only money fact you enter. Everything else is computed
  from it or compared against it.
- **Budget** splits that income into needs / wants / investment. Your first
  earning year splits into needs/wants/investment per your own base split;
  after that, only each year's *raise* is split, tilted toward investing — so
  as you earn more, a bigger share of income goes to investing. (Each person's
  exact percentages live in `config.py`; the Budget page shows yours.)
  You never type a budget; changing income changes it.
- **Allocation** is where you say how the investment slice spreads across
  instruments (mutual funds 45%, gold 25%, …). Percentages must sum to 100.
  A year's allocation carries forward until you set a newer one. It lives on
  the **Budget** page, right under the monthly split — so you can see how each
  monthly goal is consumed per instrument.
- **Actuals** is where you record what you really invested, and see it against
  the plan.

## Your page, your colours

The app shows **one person at a time**. Open it with your own link and keep it
bookmarked:

- `http://localhost:8501/?profile=rv`
- `http://localhost:8501/?profile=cheeni`

There is no switch button and no name on the page — you can tell whose page
you're on by the **accent colours** (rv: platinum grays; cheeni: rose +
raspberry, a pink family). Once set, the choice sticks as you move between
pages.

## Reading the Dashboard

Top to bottom:

1. **Four lifetime tiles** — earned to date, invested to date, what it could
   be worth today at conservative growth, and the year's **total goal**: this
   year's plan plus any shortfall carried over from past years.
2. **The journey, year on year** — bars show total income and the planned
   goal side by side; a line shows what you actually invested, so plan and
   reality read against each other at once.
3. **Allocation today** — everything you've contributed so far, split across
   instruments, stacked by the year each rupee went in (lightest = oldest).
4. **Catch up** — the closing action item. If past years fell short of the
   plan, this is the lump sum that, invested today, pulls you level. Zero (a
   calm note) means you're on plan. Investing *more* than planned is always
   fine.
6. **Health** — quiet, muted-caption nudges that only appear when something
   needs attention: no income entered yet this year, investing badly behind
   pace, an emergency fund you've never recorded, or an actual mix that's
   drifted from target. Nothing shows at all once everything's healthy.
7. **Adjustments** — a small expander at the very bottom for **opening
   corpus**: money you'd already invested before you started tracking here
   (say, ₹20L before 2024). Set it once; it's audited like every other save.
   It's assumed invested at the start of your first tracked year and grown at
   your own allocation-weighted expected return, and it counts toward
   "Invested till date" and the net-worth estimate — but it deliberately
   doesn't touch the budget, the goal, catch-up, or plan-vs-actual, since
   those are about what you've tracked, not what came before.

Everywhere in the app, the **primary accent means "what actually happened"**
and the **secondary accent means "what was planned"**.

## Rent vs buy

A calculator on its own page — nothing you enter here is saved. It frames
the decision the same way as everywhere else in the app: what's *wasted*,
not what you're worth. Buying wastes registration/stamp duty (once), loan
**interest** (never the principal — that's equity), and maintenance; renting
wastes the rent itself, inflating every year. The chart leads with that
cumulative waste, buying vs renting; a "Net position" expander below gives
the fuller picture (equity/portfolio built minus waste) with an honest note
that the assumptions — appreciation, investment return, rent inflation —
drive that number far more than the waste comparison above.

Every input starts from a sensible default and can be typed over freely —
including the investment-return assumption, which defaults to *your* target
allocation's weighted expected return. A quiet **For you** strip reads your
own income, net worth, and budget goal to say how the numbers you've entered
actually land on you: EMI as a share of your monthly income, the upfront
cost against your estimated net worth today, and what buying would eat into
your planned monthly investing. It only shows what it can actually compute
from your data, and stays out of the way otherwise.

## What to do, and when

- **Monthly (2 minutes):** nothing required — but recording contributions on
  **Actuals** as you invest beats reconstructing them in December.
- **When salary lands differently** (raise, bonus, job switch): update that
  year on **Income**. Tick "Job change this year?" if you switched jobs. A tax
  payment or clawback goes under *other* too — it's the one field allowed to
  go negative.
- **Once a year:** check the target allocation on **Actuals** still reflects
  where you want money to go; glance at **Budget** (nothing to fill — it's
  derived).
- **Zerodha for equities/MFs?** `scripts/import_tradebook.py` turns a year's
  tradebook export into one net contribution row instead of typing it in by
  hand — see the README for the command.

## Things that surprise people

- **The emergency-fund *target* is automatic** — a configured number of months
  (`EMERGENCY_FUND_MONTHS`) of your essential spending (the needs bucket); earn
  more and the target grows. What you *actually* hold is entered by hand on
  the Actuals page and counts in your net worth.
- **Saving is safe**: every save is checked first (sums, duplicates, negative
  numbers — except income's *other*, which is allowed to go negative) and
  refused with a message if something's off — and every change is also
  appended to an audit log (`changes.jsonl`), so nothing is ever silently
  lost.
- **A year you earned nothing** simply has no budget — it won't distort other
  years.
- **Catch-up means past years only** — this year's remaining goal is shown as
  "left to go", never as catch-up. (On the journey chart, the current year's
  goal bar is drawn pro-rated to the elapsed year so the bar stays fair.)
- The ₹ figures use Indian grouping and short forms: `₹55.8L` is 55.8 lakh,
  `₹3.40Cr` is 3.40 crore.
