# BAHI — the udhaar book both sides can see

At the counter, the customer scans the shop's **udhaar QR**, a separate code
beside the pay QR. The shopkeeper's Soundbox chimes, and he says the amount
("do sau") or types it. The customer confirms it on the phone already in his
hand, sees what he owes across every shop, and clears it in one tap. Every night
an agent works out, per person, when a reminder should go, and far more often,
when it should not.

Built for the **Paytm Build for India AI Hackathon, Mumbai, 3 October 2026**,
Track 2 (AI-Powered Financial Journeys).

Tickets: [BIT-8 backend](https://linear.app/bitzlab/issue/BIT-8) ·
[BIT-9 frontend](https://linear.app/bitzlab/issue/BIT-9)

---

## The problem

The udhaar book by the till is written by one person, held by one person and
read by one person. The other party to every entry has no copy.

So the shopkeeper cannot tell who is about to pay from who is drifting away, and
treats them the same. And the customer cannot see his own total, has no proof if
the number is wrong, and gets asked for money in front of other customers.
Ledger apps digitised the shopkeeper's half; the customer still gets an SMS.

## The two rules the code keeps

**No AI model ever produces a number.** The amount is parsed by rule from the
speech transcript. Every balance, gap and reminder day is plain Python in
`api/bahi/domain`, and a test fails the build if that package imports anything
outside the standard library.

**The system never guesses who.** With one person at the counter, an amount is
enough. With several, the shopkeeper says the name or taps; the Soundbox asks
"kiske liye?" rather than picking by queue order.

## The four rules we built in

Recording someone's debt and then reminding them about it runs into four Indian
laws. Each became one constraint, enforced by the database and the API rather
than by the screens.

| | Rule | How it is enforced | Why |
|---|---|---|---|
| **1** | **Acknowledge, never promise.** The button says "Yes, I owe ₹200", never "I'll pay by Friday". | `acknowledgments` has no due-date column, keeps the exact wording shown, and allows one row per entry. | A dated promise to pay can be a promissory note, which the IT Act does not cover (IT Act 2000, s.1(4) and First Schedule). |
| **2** | **Never a rupee above the price.** | No fee, interest or charge column anywhere; a test asks Postgres and fails if one appears. | State money-lending Acts define a loan by the interest it carries (e.g. Karnataka Money Lenders Act 1961, s.2(9)). |
| **3** | **Let debts die.** | Expiry is computed: three years from the sale, restarted once by the customer's confirmation. The database cannot hold a second confirmation, so the app cannot keep a debt alive by asking again. | Each written acknowledgment restarts the limitation period (Limitation Act 1963, s.18). |
| **4** | **Never shame, never charge.** | A message has no amount column; only people can type, and only BAHI posts reminders. No defaulter list. The Soundbox never says a name. | Public "defaulter" labels risk defamation (BNS 2023, s.356); repeated nudges for gain are "nagging" (CCPA Dark Patterns Guidelines 2023). |

**Record it, never fund it.** RBI's digital lending rules bind regulated
lenders and their agents; a shopkeeper giving his own trade credit is neither.
If the platform ever financed the udhaar, that could change.

## Layout

```
api/
  migrations/     the schema, as plain numbered SQL
  bahi/domain/    pure rules: money, rhythm, limitation, the book. stdlib only.
  bahi/store/     the only code that speaks SQL. Rows in, domain objects out.
  data/           migrate, seed, contract, check
  tests/
contract/         shop.json, generated from the seed for the frontend
web/              Next.js. Two mobile-first surfaces, merchant and customer.
docs/             the deck, the screens, and the scripts that build them
```

## The data model

Eight tables. What each one is for, and what is deliberately missing, is written
at the top of each table in `api/migrations/001_init.sql`.

| Table | One row is |
|---|---|
| `shops` | a kirana |
| `customers` | a person *at one shop*, linked to a Paytm account, invited, or kept by name only |
| `entries` | one udhaar; the amount never changes after it is written |
| `acknowledgments` | the customer's "Yes, I owe ₹200", at most one per entry |
| `repayments` | a payment against a named entry |
| `threads` | one conversation per shopkeeper and customer |
| `messages` | one bubble; no amount column |
| `scans` | someone at the counter, waiting for three minutes |

Balances, expiry, payment gaps and tonight's decisions are computed, never
stored. Money is `bigint` paise. We store no phone numbers.

## Running it

```
make db        create, migrate and seed; writes contract/shop.json
make db-check  read the seed back: the book, the cast, everyone's usual gap
make check     ruff, ruff format, mypy strict, pytest
make web-check tsc, eslint, vitest: no typed amounts, no shaming words, one palette
make api       the service on :8000
make web       the surfaces on :3000
```

Everything still runs with the venue wifi off: the demo clips' transcripts are
cached to disk, and with `SARVAM_OFFLINE` on (the default) our parser reads. The deployed build is what a judge's phone reaches
over its own mobile data.

## Voice

The shopkeeper says "do sau", or "Anubhav Shukla ko do sau bees" when the
customer isn't at the counter. Sarvam reads it, and our code checks every rupee:

- Sarvam's `saaras:v4` turns the audio into words, listening out for the names at
  the counter and in the book.
- Sarvam-105B reads the words: udhaar or payment, the words that state the amount,
  and the words that name the person. It picks nobody.
- `domain/check` holds that reading to the words: the amount words must be in the
  transcript, and `parse` must read them as the same number (the number recorded
  is ours, not the model's).
- `domain/who` decides the person from the words that name him, by sound, in roman
  and Devanagari. A surname or a room number ("204 wale") picks one of four
  Anubhavs; "Anubhav" alone asks "Kaunse Anubhav?"; a weak match is only offered.
- `speak` puts the amount into words, and Sarvam's `bulbul:v3` says them back
  ("दो सौ बीस रुपये", never a name); the entry goes after three seconds unless
  cancelled, and the customer confirms on his own phone.

Tapping Add udhaar opens the mic straight away, and it stops by itself a second
after he stops speaking.

Offline, or when Sarvam-105B doesn't answer, `parse` reads the words instead and
the same checks decide who. Nothing is sent by itself then: the amount and the
person are filled in, and the shopkeeper taps Send.

```
make voice-eval  the 1,338-recording test behind slide 4, replayed through today's checker
make voice       render the demo clips; with SARVAM_API_KEY in api/.env, Sarvam transcribes them
make voice-list  what the offline cache holds, and where each transcript came from
make names-hi    the seed's names in Devanagari, from Sarvam (only missing ones)
```

`make voice-eval` needs no network. On 24 Sep we spoke 42 shopkeeper lines in 12
voices, quiet, over street noise and with a second customer talking, against a
test book with 20 customers named Anubhav. With Sarvam-105B and these checks,
73.4% of entries were right from the words alone, 16.9% took one tap, 7.6% had to
be said again, and 2.1% would have gone to a phone wrong. Our parser alone, on the
same transcripts, was wrong 11.1% of the time.

## Data

Every shop, customer and amount is synthetic, generated for one seeded shop from
a fixed seed, and labelled as such on every screen. `make db` builds the same
database every time.
