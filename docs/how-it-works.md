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
  earning year splits 50/30/20; after that, only each year's *raise* splits
  20/30/50 — so as you earn more, a bigger share of income goes to investing.
  You never type a budget; changing income changes it.
- **Allocation** is where you say how the investment slice spreads across
  instruments (mutual funds 45%, gold 25%, …). Percentages must sum to 100.
  A year's allocation carries forward until you set a newer one. It's edited
  right on the **Actuals** page, not a separate stop.
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
   be worth today at conservative growth, and how far behind the plan you are
   right now (the current year counts only the fraction of it that's elapsed).
2. **The journey, year on year** — bars show total income and the planned
   goal side by side; a line shows what you actually invested, so plan and
   reality read against each other at once.
3. **Net worth chart** — an *estimate*: your contributions compounded at
   conservative expected returns, plus an emergency-fund buffer (and any
   opening corpus, see below). Not your real portfolio value.
4. **Allocation today** — everything you've contributed so far, split across
   instruments, stacked by the year each rupee went in (lightest = oldest).
5. **Catch up** — the closing action item. If past years fell short of the
   plan, this is the lump sum that, invested today, pulls you level. Zero (a
   calm note) means you're on plan. Investing *more* than planned is always
   fine.
6. **Adjustments** — a small expander at the very bottom for **opening
   corpus**: money you'd already invested before you started tracking here
   (say, ₹20L before 2024). Set it once; it's audited like every other save.
   It's assumed invested at the start of your first tracked year and grown at
   your own allocation-weighted expected return, and it counts toward
   "Invested till date" and the net-worth estimate — but it deliberately
   doesn't touch the budget, the goal, catch-up, or plan-vs-actual, since
   those are about what you've tracked, not what came before.

Everywhere in the app, the **primary accent means "what actually happened"**
and the **secondary accent means "what was planned"**.

## What to do, and when

- **Monthly (2 minutes):** nothing required — but recording contributions on
  **Actuals** as you invest beats reconstructing them in December.
- **When salary lands differently** (raise, bonus, job switch): update that
  year on **Income**. Tick "Job change this year?" if you switched jobs.
- **Once a year:** check the target allocation on **Actuals** still reflects
  where you want money to go; glance at **Budget** (nothing to fill — it's
  derived).

## Things that surprise people

- **The emergency fund is automatic** — 6 months of your "needs" bucket.
  There's nowhere to enter it; earn more, and the target grows.
- **Saving is safe**: every save is checked first (sums, duplicates, negative
  numbers) and refused with a message if something's off — and every change is
  also appended to an audit log (`changes.jsonl`), so nothing is ever silently
  lost.
- **A year you earned nothing** simply has no budget — it won't distort other
  years.
- **The current year's goal is pro-rated** — the catch-up figure only counts
  the year elapsed so far, so you're never "behind" on a raise the calendar
  hasn't reached yet.
- The ₹ figures use Indian grouping and short forms: `₹55.8L` is 55.8 lakh,
  `₹3.40Cr` is 3.40 crore.
