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
| `reminders` | a reminder Tonight drafted: its words, its hour, and the shopkeeper's Stop |

The munshi's conversations (`conversations`, `turns`, `drafts`) are in
`004_munshi.sql`; `reminders` and a new customer on the munshi's card are in
`005_tonight_and_new_customers.sql`.

Balances, expiry, payment gaps and tonight's decisions are computed, never
stored. Money is `bigint` paise. We store no phone numbers.

## Running it

```
make db        create, migrate and seed; writes contract/shop.json
make db-check  read the seed back: the book, the cast, everyone's usual gap
make decide    tomorrow's reminders: who is sent one, who is held, and why
make check     ruff, ruff format, mypy strict, pytest
make web-check tsc, eslint, vitest: no typed amounts, no shaming words, one palette
make api       the service on :8000
make web       the surfaces on :3000
```

The book, the scan-to-confirm loop and entering by hand run with the venue wifi
off. The munshi needs Sarvam: set `SARVAM_OFFLINE=0` and `SARVAM_API_KEY` in
`api/.env`. The deployed build is what a judge's phone reaches over its own mobile
data.

## The munshi: voice and chat

The shopkeeper talks or types to the munshi, the shop's bookkeeper as an agent:
"बी विंग में जो रहते हैं उनके नाम दो सौ लिख दो", "दूध वाले भैया ने पाँच सौ दिए",
"Sharma took goods for 200". The AI does the work, code keeps the book, and both
people approve.

- Sarvam's `saaras:v4` turns his voice into words, with the book's names as hints.
- `sarvam-105b-conversations` (Sarvam's model for voice agents; thinking off, and
  `sarvam-105b` asked too if it is slow) understands him and calls tools
  (`munshi/tools.py`): `find_customer` searches the real book by the sound of a
  name and the words of a description (`domain/find`), `counter` and
  `customer_card` read it, and `propose_entry` puts a card on his screen.
- When three or more customers fit, it asks "नाम बताऊँ, या आप बताएँगे?" and
  reads names only if asked. It never says anyone's balance unless asked.
- The card shows the amount as stored, not the munshi's sentence, with his words
  under it. An ordinary entry goes after three seconds unless he says or taps no;
  a name that only sounded close, ₹5,000 or more, or three times what the customer
  usually takes waits for a clear हाँ.
- Only his yes writes, through the same ledger as a typed entry: udhaar becomes an
  entry, and जमा is split across the customer's open entries, oldest first. Then
  the munshi says whether it reached the customer's phone, from what the book
  reports. The customer still confirms on his own phone.
- Every turn (his words, each tool call and result, each reply, and how long the
  model took) is kept in `turns`, so any conversation can be traced.

The munshi needs Sarvam. Offline, the screen's keypad and book still record by
hand. Its replies are spoken in Sarvam's `bulbul:v3` voice (`shreya`).

```
make munshi-eval another model plays the shopkeeper with a hidden goal; scored on
                 the entry the book would hold (live Sarvam, rolled back, costs credits)
```

## The whole loop

Both screens update every two seconds, so the shopkeeper's laptop and the
customer's phone move together.

**Chat** (`/m/messages`, `/m/chat/…`, `/c/chat/…`). One thread per shop and
customer. People type; BAHI posts each entry's card, drawn from the entry as it
is now, so ₹200 posted this morning shows ✓ the moment he confirms. The customer
answers an entry in the thread: "Yes, I owe ₹200", or "That's not right" with his
reason. The shopkeeper answers a dispute with Correct the amount, which records a
new entry that points at the old one; the old one is kept, marked corrected, and
the customer confirms the new one himself. When the customer wrote last, the
munshi suggests two replies in his language, and nothing goes until the
shopkeeper taps one. A message has nowhere to carry an amount: the Pay button
comes from the customer's own entries.

**The customer's own book** (`/c/udhaar`). What he owes across every shop he is
in the book of, each entry, and Pay: everything he owes that shop, by UPI, each
entry named. A disputed entry waits until it is agreed, and an expired one is
shown struck through, claiming nothing. Then Cleared, and what is still open
elsewhere. The demo's customer side asks whose phone it is: Sharma owes three
shops.

**Someone who can't scan** (`/m/customers/new`). A mobile number or UPI ID finds
the Paytm account (a synthetic directory, `data/directory.py`, stands in for
Paytm's lookup, and the number is never kept); the invite waits on their phone,
and nothing is recorded until they accept. No phone: kept by name only. Or tell
the munshi, "रमेश को पाँच सौ", and when nobody fits it asks whether he is new, then
puts "Ramesh · New · Chawl 7 · ₹500" on a card that waits for a clear हाँ.

**The Soundbox.** The shopkeeper's screens ask `/events` every two seconds: a
scan chimes, a yes plays a done tone, a dispute asks its question tone, a message
pings, and money arriving is said aloud ("दो सौ रुपये"). It never says a name; the
strip on the screen shows who.

**Tomorrow** (`/m/tonight`, and "कल किसको याद दिलाना है?" to the munshi). Code
decides, from each customer's own history (`domain/tonight.py`): a reminder goes
only to someone past the longest gap they have ever had, at the hour they usually
pay, between 9 am and 8 pm. Everyone else is held, and the reason is named: inside
their own gap, an entry they haven't confirmed or say is wrong, too new to read,
kept by name only, or reminded within their gap. On the seed that is 4 of 38:
Patil at 10 am, Iqbal at 6:30 pm, Raju and Salma at 8 pm. The munshi writes each
reminder in the customer's words; our code refuses one that names any figure but
their balance, so it can never carry a date or another sum, and falls back to our
own sentence. The shopkeeper can stop any of them. `POST /tonight` is the 11 pm
run and `POST /tonight/send` sends each at its hour; n8n will call both (V8a).
Until then, Send now posts them at once for the demo.

## Voice before the munshi

The V2 path is still in the code, though no longer on the screen: Sarvam-105B read
the words, `domain/check` held its amount to the words, and `domain/who` decided
the person. The numbers below measured that path.

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

Replayed through today's checker, which also reads the tag, 75.0% are right from
the words alone and 15.3% take one tap; nothing is graded worse than on the day,
and the test fails if anything ever is.

## Data

Every shop, customer and amount is synthetic, generated for one seeded shop from
a fixed seed, and labelled as such on every screen. `make db` builds the same
database every time.
