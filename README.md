# BAHI — the udhaar book both sides can see

A kirana shopkeeper records credit by speaking to his Soundbox. The customer
confirms it on his own phone, sees his own balance across every shop he owes,
and clears it in one tap. Every night the agent works out, per person, when a
reminder should go — and, far more often, when it should not.

Built for the **Paytm Build for India AI Hackathon, Mumbai, 3 October 2026**,
Track 2 (AI-Powered Financial Journeys).

Tickets: [BIT-8 backend](https://linear.app/bitzlab/issue/BIT-8) ·
[BIT-9 frontend](https://linear.app/bitzlab/issue/BIT-9)

---

## The problem

About 1.3 crore kirana shops in India run a credit book by the till. It is
written by one person, held by one person, and read by one person. The other
party to every entry has no copy.

So the shopkeeper cannot tell who is about to pay from who is drifting away,
and treats them identically. And the customer cannot see his own total, holds
no evidence if the number is wrong, and gets asked for money in front of other
customers — because embarrassment is the only enforcement anyone has built.

## The one rule

**No language model ever produces a number.**

The amount is parsed by rule from the speech transcript. The rhythm, the gap,
the reminder day, every balance — deterministic Python. The model writes prose
around figures it did not compute, and nothing else. This must be
demonstrable in ten seconds on stage.

## The four rules we built in

Recording someone's debt and then reminding them about it walks into four
separate Indian statutes. Each one became a single implementation constraint,
enforced in the schema and the API rather than in the UI — a UI that merely
behaves well is a styling choice.

| | Rule | Where it lives |
|---|---|---|
| **1** | **Acknowledge, never promise.** The button says "I owe ₹200", never "I'll pay by Friday". | No due-date field on the acknowledgment record. IT Act 2000 s.4 recognises an acknowledgment; a promise to pay a fixed sum is a demand promissory note, First Schedule entry 1, which sits outside the Act entirely. |
| **2** | **Never a rupee above the price.** | No fee, interest or charge column anywhere in the schema. All four state Money-Lenders Acts define a loan as an advance "at interest"; one ₹10 late fee makes the shopkeeper an unlicensed money-lender in Karnataka and Delhi. |
| **3** | **Let debts die.** | `claimable_until` = last acknowledgment + 3 years. The scheduler stops prompting before the clock runs out, and the entry is marked expired to both sides. Limitation Act s.18 restarts a fresh three years on every acknowledgment, with no cap — an app that keeps prompting makes a ₹200 debt legally immortal. The paper diary let it die. |
| **4** | **Never shame, never charge.** | No demand endpoint for the merchant, no defaulter list, no shared blacklist, no commercial payload on a reminder. CCPA's "nagging" needs repetition *and* commercial gain; BNS s.308 Illustration (a) makes threatening exposure to extract payment the textbook case of extortion. The customer gets a pay action; the shopkeeper gets a text field. |

Regulatory position: RBI's Digital Lending Directions 2025 para 3 bind
Regulated Entities only, and an LSP is "an agent of a RE" — a kirana
shopkeeper is not one. CICRA does not reach us either, because "credit
information" under s.2(d) is defined by reference to credit granted *by a
credit institution*. **Record it, never fund it** — the moment the platform
finances the udhaar, CICRA s.2(f)(vi) flips the perimeter.

## Layout

```
api/          FastAPI + Postgres. Owns the ledger and every figure.
  bahi/       the service
  data/       schema, migrations, seed generator
  tests/
web/          Next.js. Two mobile-first surfaces, merchant and customer.
docs/         the deck, the canvas, the screens
```

## Running it

```
make db        drop, migrate, seed — one shop, 60 udhaar customers, 6 months
make api       the service on :8000
make web       the surfaces on :3000
make check     ruff, mypy strict, pytest
```

Everything runs with the venue wifi off: Sarvam responses are cached to disk
and `SARVAM_OFFLINE` defaults on. The deployed build is what a judge's phone
reaches over its own mobile data.

## Data

All figures are synthetic, generated for one seeded shop, and labelled as such
on every screen. Paytm does not publish udhaar volume and neither does anyone
else — we looked.
