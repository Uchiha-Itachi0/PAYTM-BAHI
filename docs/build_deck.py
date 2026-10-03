"""
BAHI — Round 1 deck.

Ten slides: the seven sections the organisers mandate, in their order, then
three value-adds. Same 7+3 shape as a team we found who was shortlisted.

Two things drive the design.

1. THIS DECK IS READ, NOT PRESENTED. It is the eliminator stage — a reviewer
   opens the PDF without us in the room and decides in about ninety seconds.
   So it carries its own argument: dense, self-contained, every claim sourced.
   A sparse "presentation" deck would be the wrong artefact entirely.

2. IT SHOULD LOOK LIKE PAYTM. Pale sky ground, floating white cards at 16px
   radius, navy headings, cyan as a rule or mark and never as text (#00BAF2
   is ~2.0:1 on white). That is the app's own language, and a deck about a
   feature inside Paytm should read as if it belongs there.
"""

from __future__ import annotations

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ── Paytm palette ──────────────────────────────────────────────────────────
NAVY = RGBColor(0x00, 0x29, 0x70)
NAVY_2 = RGBColor(0x0F, 0x2E, 0x7E)
CYAN = RGBColor(0x00, 0xBA, 0xF2)
CYAN_TX = RGBColor(0x00, 0x77, 0xA8)
SKY = RGBColor(0xEA, 0xF6, 0xFC)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
INK = RGBColor(0x1C, 0x1C, 0x1C)
MUTED = RGBColor(0x5B, 0x66, 0x75)
FAINT = RGBColor(0x8B, 0x95, 0xA5)
HAIR = RGBColor(0xD9, 0xE4, 0xEC)
GREEN = RGBColor(0x1E, 0x7E, 0x34)
AMBER = RGBColor(0xA8, 0x62, 0x0A)
RED = RGBColor(0xB3, 0x26, 0x1E)

F = "Arial"

W, H = Inches(13.333), Inches(7.5)
ML = Inches(0.62)
CW = W - Inches(1.24)
GUT = Inches(0.24)

Y_EYE = Inches(0.40)
Y_TITLE = Inches(0.70)
H_TITLE = Inches(0.92)
Y_STAND = Inches(1.70)
H_STAND = Inches(0.78)
Y_CARDS = Inches(2.50)
Y_FOOT = H - Inches(0.44)

prs = Presentation()
prs.slide_width, prs.slide_height = W, H
BLANK = prs.slide_layouts[6]


# ── primitives ─────────────────────────────────────────────────────────────
def slide(bg=SKY):
    s = prs.slides.add_slide(BLANK)
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H)
    r.fill.solid(); r.fill.fore_color.rgb = bg
    r.line.fill.background(); r.shadow.inherit = False
    return s


def rect(s, x, y, w, h, color, shape=MSO_SHAPE.RECTANGLE, radius=None):
    r = s.shapes.add_shape(shape, x, y, w, h)
    r.fill.solid(); r.fill.fore_color.rgb = color
    r.line.fill.background(); r.shadow.inherit = False
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        r.adjustments[0] = radius
    return r


def tb(s, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    box = s.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    return tf


def para(tf, text, size, color=INK, bold=False, italic=False, line=1.34,
         after=0, before=0, first=False, align=None, spc=None):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.text = text
    p.line_spacing = line
    p.space_after = Pt(after)
    p.space_before = Pt(before)
    if align:
        p.alignment = align
    for r in p.runs:
        r.font.size = Pt(size)
        r.font.color.rgb = color
        r.font.name = F
        r.font.bold = bold
        r.font.italic = italic
        if spc is not None:
            r.font._rPr.set("spc", str(int(spc * 100)))
    return p


def eyebrow(s, text):
    tf = tb(s, ML, Y_EYE, CW, Inches(0.24))
    para(tf, text.upper(), 9.5, CYAN_TX, bold=True, first=True, spc=1.4)


def title(s, text, size=30):
    tf = tb(s, ML, Y_TITLE, CW, H_TITLE)
    para(tf, text, size, NAVY, bold=True, first=True, line=1.06)


def standfirst(s, text, size=12.5, w=Inches(11.4)):
    tf = tb(s, ML, Y_STAND, w, H_STAND)
    para(tf, text, size, MUTED, first=True, line=1.38)


def footer(s, text, color=FAINT):
    tf = tb(s, ML, Y_FOOT, CW, Inches(0.26))
    para(tf, text, 8.5, color, first=True, line=1.25)


def card(s, x, y, w, h, head, lines, head_color=NAVY, accent=CYAN,
         head_size=12.5, body_size=10, bullets=True):
    """A floating white card: cyan rule, heading, body."""
    rect(s, x, y, w, h, WHITE, MSO_SHAPE.ROUNDED_RECTANGLE, 0.055)
    rect(s, x + Inches(0.20), y + Inches(0.20), Inches(0.34), Pt(2.5), accent)
    tf = tb(s, x + Inches(0.20), y + Inches(0.33), w - Inches(0.40), Inches(0.4))
    para(tf, head, head_size, head_color, bold=True, first=True, line=1.14)
    tf = tb(s, x + Inches(0.20), y + Inches(0.74), w - Inches(0.40), h - Inches(0.94))
    for i, ln in enumerate(lines):
        bold = ln.startswith("**")
        txt = ln.replace("**", "")
        para(tf, txt, body_size, INK if bold else MUTED, bold=bold,
             first=(i == 0), line=1.32, after=5)


def cards(s, items, y=Y_CARDS, h=Inches(4.44), head_size=12.5, body_size=10):
    n = len(items)
    cw = int((CW - GUT * (n - 1)) / n)
    for i, (head, lines) in enumerate(items):
        card(s, ML + i * (cw + GUT), y, cw, h, head, lines,
             head_size=head_size, body_size=body_size)


# ═══════════════════════════════════════════════════════════════════════════
# 1 · TITLE
# ═══════════════════════════════════════════════════════════════════════════
s = slide(NAVY)
rect(s, 0, 0, W, Pt(8), CYAN)

tf = tb(s, ML, Inches(2.24), Inches(11), Inches(1.4))
para(tf, "BAHI", 74, WHITE, bold=True, first=True, line=0.98)
rect(s, ML, Inches(3.48), Inches(1.4), Pt(3.5), CYAN)

tf = tb(s, ML, Inches(3.76), Inches(10.6), Inches(0.62))
para(tf, "The udhaar book both sides can see.", 25, WHITE, bold=True,
     first=True, line=1.14)

tf = tb(s, ML, Inches(4.52), Inches(10.4), Inches(1.2))
para(tf, "A kirana shopkeeper records credit by speaking to his Soundbox. The "
         "customer confirms it on his own phone, sees what he owes across every "
         "shop, and clears it in one tap. Every night the agent works out, per "
         "person, when a reminder should go — and, far more often, when it "
         "should not.",
     13, RGBColor(0xAF, 0xC3, 0xE2), first=True, line=1.46)

rect(s, ML, Inches(5.92), CW, Pt(0.9), RGBColor(0x1C, 0x44, 0x8C))
tf = tb(s, ML, Inches(6.14), CW, Inches(0.9))
para(tf, "Paytm Build for India AI Hackathon  ·  Mumbai  ·  3 October 2026",
     11.5, WHITE, bold=True, first=True)
para(tf, "Track 2 — AI-Powered Financial Journeys", 11.5, CYAN, bold=True,
     before=3)
para(tf, "Team Bitzlab", 10.5, RGBColor(0x8F, 0xA4, 0xC6), before=3)

# ═══════════════════════════════════════════════════════════════════════════
# 2 · PROBLEM STATEMENT
# ═══════════════════════════════════════════════════════════════════════════
s = slide()
eyebrow(s, "1 · Problem statement")
title(s, "The notebook has one author and two people’s money in it.")
standfirst(s, "About 1.3 crore kirana shops in India run a credit book by the "
              "till. It is written by one person, held by one person, and read "
              "by one person. The other party to every entry — the person whose "
              "debt it is — has no copy, no record and no way to disagree.")
cards(s, [
    ("The scale, and what nobody knows", [
        "**~1.3 crore kirana stores in India.** 88% of retail is unorganised "
        "and 95% of kirana transactions are under ₹200 (Invest India).",
        "A shop of 400 customers typically carries 30–60 on udhaar at any time.",
        "**No credible figure exists for udhaar volume.** Not from RBI, not the "
        "NSS, not any major consultancy — we looked hard. The largest pool of "
        "informal credit in the country is unmeasured.",
        "That absence is itself the finding."]),
    ("What the shopkeeper cannot see", [
        "**Who is about to pay, and who is drifting away.** They look identical "
        "in a notebook, so he treats them identically.",
        "Sharma has paid on day 9 for two years. Asked on day 4, he hears an "
        "accusation — and the relationship is the collateral.",
        "Patil has quietly reached day 40 — but he stopped coming in, so he is "
        "out of sight and gets asked nothing.",
        "**The one who needs chasing is invisible; the one who doesn’t gets "
        "chased.**"]),
    ("What the customer cannot see", [
        "**His own total.** He owes at three shops and could not tell you the "
        "sum within ₹500.",
        "**Any evidence.** If the book says ₹500 where he remembers ₹300, there "
        "is no entry, no date, no timestamp. He simply loses the argument.",
        "When he will be asked, and how loudly.",
        "The record is one-sided, so the argument is one-sided too."]),
    ("How it is enforced today", [
        "**In public.** Being asked for money in front of other customers is "
        "the enforcement mechanism — and it works, which is why it persists.",
        "Collecting the money costs the customer something that is not money.",
        "**The software makes it worse.** One live Indian product sells "
        "shopkeepers “instant community alerts when a chronic non-payer enters "
        "your neighborhood”.",
        "Under BNS s.308 that is close to extortion. It is also the state of "
        "the art."]),
])
footer(s, "Sources: Invest India (store count, ticket size); Google Play "
          "listings and company sites for competing products. Named merchants "
          "throughout this deck are synthetic demo data.")

# ═══════════════════════════════════════════════════════════════════════════
# 3 · PROPOSED SOLUTION  (with screens)
# ═══════════════════════════════════════════════════════════════════════════
s = slide()
eyebrow(s, "2 · Proposed solution")
title(s, "The same notebook, with a second reader.")
standfirst(s, "Five steps. Only one of them asks the shopkeeper to do anything "
              "he is not already doing — and that one he does by speaking, "
              "because his hands are full and there is a queue.")

SHOT_W = Inches(1.92)
SHOT_H = Inches(3.80)
shots = [
    ("docs/screens/A2-speak.png", "He speaks it",
     "“Sharma ko do sau udhaar.” Sarvam hears it; a rule — not the model — "
     "extracts ₹200. The parsed fields are shown for checking before anything "
     "is sent."),
    ("docs/screens/B1-confirm.png", "The customer confirms",
     "A sheet inside his own Paytm app. Confirming turns a private claim into "
     "a mutual record. Declining opens a chat, and the entry stays in the "
     "shopkeeper’s book marked unconfirmed."),
    ("docs/screens/A3-tonight.png", "The agent picks the day",
     "Arithmetic over that one person’s own history. Sharma is on day 4 and "
     "pays on day 9, so nothing is sent. Four of thirty-eight get a message."),
]
cx = ML
for path, head, body in shots:
    s.shapes.add_picture(path, cx, Y_CARDS, width=SHOT_W, height=SHOT_H)
    tf = tb(s, cx + SHOT_W + Inches(0.20), Y_CARDS + Inches(0.06),
            Inches(1.86), Inches(3.6))
    para(tf, head, 12.5, NAVY, bold=True, first=True, line=1.14)
    para(tf, body, 10, MUTED, before=6, line=1.34)
    cx += Inches(4.13)

rect(s, ML, Inches(6.62), CW, Pt(1), HAIR)
tf = tb(s, ML, Inches(6.78), CW, Inches(0.4))
para(tf, "Step 1 — he joins by scanning a QR at the till, so the shopkeeper "
         "never types a stranger’s number.     Step 5 — the reminder carries a "
         "UPI button; one tap closes the entry on both sides at once.",
     10, MUTED, first=True, line=1.34)

# ═══════════════════════════════════════════════════════════════════════════
# 4 · TECH STACK
# ═══════════════════════════════════════════════════════════════════════════
s = slide()
eyebrow(s, "3 · Technology / tech stack used")
title(s, "Every figure is computed. None is generated.")
standfirst(s, "Our central claim is that no language model ever produces a "
              "number. A promise is worthless, so the architecture is shaped to "
              "make it provable in ten seconds — by running one test, in front "
              "of you.")
cards(s, [
    ("The architecture", [
        "**Ports and adapters, four layers.**",
        "**domain/** — pure. Frozen dataclasses and functions. No database, no "
        "HTTP, no model. Money in, money out.",
        "**store/** — the only module importing psycopg.",
        "**speech/** — the only module calling Sarvam.",
        "**service/** — the only module importing FastAPI.",
        "**One test enforces it:** an AST check fails the build if anything in "
        "domain/ imports outside the standard library. That is how we prove the "
        "model cannot reach the arithmetic."]),
    ("The stack, and why", [
        "**FastAPI** — validation is declarative via Pydantic, and the OpenAPI "
        "spec is generated from the same type hints, so the frontend contract "
        "is derived from the implementation. No schema drift.",
        "**Sync handlers, deliberately** — async pays at thousands of "
        "connections; we have two. It would cost function colouring and a class "
        "of missing-await bugs for throughput we cannot use.",
        "**Postgres 17** — SQLite lives on the container’s ephemeral "
        "filesystem, so a restart mid-demo would erase a judge’s confirmation.",
        "**Raw SQL, no ORM** — the rhythm query is the product, and we want it "
        "readable."]),
    ("How the model is kept out", [
        "**Sarvam returns a string. A rule returns the number.**",
        "speech/asr.py gets back the text “Sharma ko do sau udhaar”.",
        "domain/parse.py turns that text into 20000 paise, by rule.",
        "The model never sees the amount field and cannot influence it.",
        "**So the worst case is visible, not silent.** If it mishears, the "
        "merchant sees the wrong words on screen and taps “Say it again”. There "
        "is no path where a wrong number is recorded quietly.",
        "Every spoken line is cached to disk; the demo runs with the wifi off."]),
    ("The three sponsor tools", [
        "**Sarvam** — saaras:v4 for speech in mixed Hindi-English over shop "
        "noise, bulbul:v3 to read a balance back. Pinned deliberately: v2 of "
        "both was retired and now returns 400.",
        "**Cognee** — holds each customer’s rhythm and the shopkeeper’s "
        "standing instructions (“Patil is a daily wager, he pays after the "
        "10th”). The rhythm is arithmetic; Cognee remembers the instructions.",
        "**n8n** — the 11pm schedule. Honestly: a cron line would do the same "
        "job. What n8n buys is that the schedule becomes a canvas you can look "
        "at. The logic stays in Python."]),
], body_size=9.5)
footer(s, "Postgres 17 · psycopg 3 · FastAPI · Python 3.13 under uv · ruff · "
          "mypy strict · pytest  ·  Next.js 16 · React 19 · mobile-first web, "
          "deployed publicly so a judge’s phone reaches it over its own data.")

# ═══════════════════════════════════════════════════════════════════════════
# 5 · USP
# ═══════════════════════════════════════════════════════════════════════════
s = slide()
eyebrow(s, "4 · Unique selling proposition")
title(s, "Every ledger app in India is one-sided. On purpose.")
standfirst(s, "Khatabook has 5 crore shopkeepers and no customer app. OkCredit "
              "advertises the absence — “Customer ko app ki zaroorat nahi.” "
              "Paytm’s own Business Khata shipped in 2020, one-sided, and now "
              "sits orphaned off its product nav. We are proposing the half "
              "none of them built.")
cards(s, [
    ("Two-sided, by consent", [
        "**The customer confirms the entry.** That single change turns a "
        "private assertion into a mutual record.",
        "An unconfirmed entry is a claim. A confirmed one is a fact. The "
        "shopkeeper keeps both — he never loses his own book.",
        "It is also how a platform discharges **DPDP s.8(3)**, the duty to "
        "ensure data used to make a decision about a person is complete and "
        "accurate, which binds from May 2027.",
        "Every competitor sends a one-way notification instead."]),
    ("Voice, where it is necessary", [
        "**Paytm’s AI Soundbox grew a microphone in October 2025** and already "
        "takes spoken questions in 11 languages.",
        "Three companies are building on that rail — Paytm, ToneTag, Razorpay "
        "with Sarvam. **Nobody has pointed it at credit.**",
        "The hardware is already on the counter, already paid for, and idle for "
        "this purpose.",
        "This is the one place in the product where voice is not decoration: "
        "his hands are full and there is a queue behind the customer."]),
    ("Timing, not blacklisting", [
        "**“Sharma pays on day 9. Do not chase before day 7.”**",
        "Per-customer repayment timing exists in formal collections — "
        "TrueAccord’s cadence optimizer, Credgenics — and **nowhere in informal "
        "credit**, anywhere in the world.",
        "What exists in the Indian long tail instead is the shared defaulter "
        "list. We are the humane inverse of a product that already ships.",
        "**The measure of success is how few messages go out.** Four of "
        "thirty-eight, not thirty-eight of thirty-eight."]),
    ("Built legal-first", [
        "Recording a debt and then reminding someone about it walks into four "
        "separate Indian statutes.",
        "We read them before we built, and **each became one implementation "
        "constraint** — enforced in the schema and the API, not in the UI.",
        "That is why there is no due-date field, no fee column, and no endpoint "
        "that lets a merchant demand money in one tap.",
        "**No competitor in this category has done this.** See slide 8 — it is "
        "the most defensible thing we have."]),
], body_size=9.5)

# ═══════════════════════════════════════════════════════════════════════════
# 6 · IMPACT & BENEFITS
# ═══════════════════════════════════════════════════════════════════════════
s = slide()
eyebrow(s, "5 · Impact & benefits")
title(s, "Three parties, and none of them loses.")
standfirst(s, "The shopkeeper keeps his money and his customer. The customer "
              "gets a copy of his own obligations for the first time. Paytm "
              "gets settlement volume that is currently paid in cash and is "
              "therefore invisible to it.")
cards(s, [
    ("The shopkeeper", [
        "**Stops chasing the people who were always going to pay** — and "
        "notices the ones who have genuinely changed.",
        "On our seeded shop that is 4 messages instead of 38.",
        "Keeps his record intact whether or not the customer confirms.",
        "Recovers money **without spending the relationship**, which today is "
        "the real price of asking.",
        "Records by speaking, so nothing slows the queue down.",
        "A dispute becomes a two-minute conversation with a timestamp, instead "
        "of his word against theirs."]),
    ("The customer", [
        "**Sees his total across every shop he owes — for the first time.** A "
        "number he genuinely does not have today.",
        "**Holds evidence.** A disputed amount stops being his word against a "
        "notebook.",
        "Is reminded privately on day 7 instead of publicly on day 15.",
        "**His debts are allowed to expire**, rather than being kept alive "
        "indefinitely by our own prompts.",
        "And a year of reliable repayment becomes the only evidence of "
        "creditworthiness he will ever have."]),
    ("Paytm", [
        "**Udhaar is settled in cash today.** Every entry cleared through BAHI "
        "is a UPI transaction that did not previously exist — new volume and "
        "MDR, not cannibalised volume.",
        "**Soundbox retention.** The device stops being a payment announcer and "
        "becomes the place the credit book lives. Churn on that subscription is "
        "the metric this moves.",
        "A reason for the consumer app to be opened by people who currently "
        "only scan and pay.",
        "**Record it, never fund it.** The moment the platform finances the "
        "udhaar, CICRA s.2(f)(vi) turns it into a credit institution."]),
], body_size=10)

# ═══════════════════════════════════════════════════════════════════════════
# 7 · BUSINESS MODEL
# ═══════════════════════════════════════════════════════════════════════════
s = slide()
eyebrow(s, "6 · Business model")
title(s, "The ledger is not the product. The settlement is.")
standfirst(s, "We are not going to pretend this category monetises by "
              "subscription, because it demonstrably does not — and a judge who "
              "knows Indian fintech will know that before we finish the "
              "sentence.")
cards(s, [
    ("What the category proved", [
        "**OkCredit:** 10 crore downloads → ₹23 crore revenue. Monetises at "
        "₹30/month. Last equity round 2019.",
        "**Khatabook:** $187M raised, $600M valuation in Aug 2021, **no round "
        "since**. FY24 revenue ₹102.7 crore against a ₹116 crore loss.",
        "**Lummo (Indonesia):** 6.3 million merchants, $25.9B annualised volume "
        "— 2.2% of Indonesian GDP — and $140M from Tiger, Sequoia and Bezos. "
        "**Voluntarily liquidated in 2023 and returned $70M.**",
        "**The ledger has never been the business.** Anyone selling one as a "
        "business is not reading the record."]),
    ("What we charge", [
        "**Nothing.** Not the shopkeeper, not the customer, and — critically — "
        "nothing on the reminder itself.",
        "That last one is a legal constraint rather than generosity: the CCPA’s "
        "“nagging” dark pattern requires repetition **and** commercial gain. A "
        "reminder cadence supplies the repetition inherently, so we refuse to "
        "supply the gain.",
        "No subscription, no per-message fee, no lending upsell riding on a "
        "debt reminder.",
        "This also removes the incentive to send more messages than necessary — "
        "which is the failure mode of every collections product."]),
    ("Where the money actually is", [
        "**Udhaar settles in cash.** It is one of the largest pools of payment "
        "volume in India that has never touched a rail.",
        "Every entry cleared in-app is **incremental UPI volume and MDR** on "
        "transactions Paytm does not see at all today. Not moved from "
        "elsewhere — created.",
        "A 400-customer shop carrying ~₹14,000 of udhaar at any time, settling "
        "monthly, is ~₹1.7 lakh a year of newly-visible volume from one store.",
        "Multiply by a device base already installed."]),
    ("What it defends, and unlocks", [
        "**Soundbox subscription retention.** A merchant whose credit book "
        "lives in the device does not churn off the device. That is a line "
        "Paytm already sells and already measures.",
        "**Consumer app engagement** from a cohort that currently only scans a "
        "QR and leaves.",
        "**Later, deliberately later:** a repayment record for people with no "
        "bureau file. Recording sits outside CICRA; financing does not, so this "
        "is a data asset and not a lending product.",
        "We would rather say that plainly than overclaim it."]),
], body_size=9.5)

# ═══════════════════════════════════════════════════════════════════════════
# 8 · THE FOUR RULES
# ═══════════════════════════════════════════════════════════════════════════
s = slide()
eyebrow(s, "How we designed it — four rules from four statutes")
title(s, "Recording a debt is easy. Recording it safely is the product.")
standfirst(s, "Every product in this category walks into the same four Indian "
              "statutes. We read them first, and each one became a single "
              "implementation constraint rather than a disclaimer at the bottom "
              "of a screen.")
cards(s, [
    ("Rule 1 — acknowledge, never promise", [
        "**IT Act 2000, s.4 and First Schedule**",
        "The button says “Yes, I owe ₹200”. It must never say “I’ll pay by "
        "Friday”.",
        "An acknowledgment of debt is recognised electronically. A promise to "
        "pay a fixed sum is a **demand promissory note** — a negotiable "
        "instrument, First Schedule entry 1, which puts the record outside the "
        "IT Act entirely.",
        "**In the schema: there is no due-date column on an acknowledgment.** "
        "Not unused — absent, so nobody adds it later as a convenience."]),
    ("Rule 2 — never a rupee above the price", [
        "**State Money-Lenders Acts**",
        "No late fee, no convenience charge, no interest, ever.",
        "All four state Acts define a loan as an advance “at interest”, of "
        "money **or in kind**. Maharashtra catches “any sum, by whatsoever name "
        "called, in excess of the principal”.",
        "Karnataka and Delhi have **no trade-credit exclusion** — one ₹10 late "
        "fee makes the shopkeeper an unlicensed money-lender there.",
        "**In the schema: no fee, charge or interest column exists anywhere.**"]),
    ("Rule 3 — let debts die", [
        "**Limitation Act 1963, s.18**",
        "Every acknowledgment restarts a fresh three years, **with no cap on "
        "restarts**.",
        "So an app that keeps prompting converts a ₹200 debt from 2023 into one "
        "that is legally immortal. The paper diary let it die; we would be "
        "taking that away.",
        "**We stop prompting before the clock runs out**, mark the entry "
        "expired, and show it struck through to both sides.",
        "Nobody else in this category shows a debt ending."]),
    ("Rule 4 — never shame, never charge", [
        "**BNS 2023 s.308 · CCPA Dark Patterns 2023**",
        "BNS s.308, Illustration (a): threatening to expose someone unless they "
        "pay **is the textbook definition of extortion**. Seven years.",
        "That is our nearest competitor’s entire business model.",
        "So: no defaulter list, no blacklist, no leaderboard, no sorting by who "
        "owes most.",
        "**In the API: no endpoint lets the merchant demand money.** The customer "
        "gets a pay button; the shopkeeper gets a text field."]),
], body_size=9.5)
footer(s, "Also cleared: RBI’s Digital Lending Directions 2025 bind Regulated "
          "Entities only (para 3) — a shopkeeper is not one. CICRA does not "
          "apply either.",
       MUTED)

# ═══════════════════════════════════════════════════════════════════════════
# 9 · THE FIELD
# ═══════════════════════════════════════════════════════════════════════════
s = slide()
eyebrow(s, "The field — what already exists, and what it chose not to do")
title(s, "The gap is not an oversight. It is a decision everyone made.")
standfirst(s, "Tens of millions of shopkeepers already use a free digital "
              "udhaar ledger. Not one of them gives the customer a say. The "
              "consent step is the product.")

COLS = [Inches(2.35), Inches(1.55), Inches(1.75), Inches(1.60), Inches(1.65), Inches(2.72)]
HEADS = ["", "Scale", "Customer app", "Confirms?", "Timing", "What it chose"]
ROWS = [
    ("Khatabook", "5 crore users", "No", "No", "No",
     "Pivoted to loan distribution; ledger is the funnel"),
    ("OkCredit", "1 crore installs", "No — by design", "No", "No",
     "“Customer ko app ki zaroorat nahi”; ₹30/month"),
    ("Paytm Business Khata", "Since Jan 2020", "No", "No", "No",
     "Orphaned — absent from Paytm’s own product nav"),
    ("BukuWarung (ID)", "8M merchants", "No", "Notification only", "No",
     "Warns that the notification gets misused for fraud"),
    ("DukanWala", "Small", "No", "No", "No",
     "Shared defaulter alerts — the adversarial inverse"),
    ("“Done” app", "100+ installs", "Yes", "Yes — OTP/PIN", "No",
     "Built the mechanic. No distribution, so nobody saw it"),
    ("BAHI", "—", "Inside Paytm", "Yes", "Yes",
     "Both halves already installed on both phones"),
]

ty = Inches(2.60)
x = ML
for w, head in zip(COLS, HEADS):
    if head:
        tf = tb(s, x + Inches(0.02), ty, w, Inches(0.3))
        para(tf, head.upper(), 8.5, CYAN_TX, bold=True, first=True, spc=1.0)
    x += w
ty += Inches(0.3)
rect(s, ML, ty, CW, Pt(1.5), CYAN)
ty += Inches(0.10)

for r, row in enumerate(ROWS):
    last = r == len(ROWS) - 1
    rh = Inches(0.56)
    if last:
        rect(s, ML - Inches(0.08), ty - Inches(0.04), CW + Inches(0.16),
             rh + Inches(0.02), WHITE, MSO_SHAPE.ROUNDED_RECTANGLE, 0.14)
    x = ML
    for c, (w, val) in enumerate(zip(COLS, row)):
        tf = tb(s, x + Inches(0.02), ty + Inches(0.06), w - Inches(0.08),
                Inches(0.48))
        if c == 0:
            para(tf, val, 10.5, NAVY if last else INK, bold=True, first=True,
                 line=1.16)
        elif c == 5:
            para(tf, val, 8.8, MUTED, first=True, line=1.22)
        else:
            col = GREEN if val.startswith("Yes") else (
                RED if val.startswith("No") else MUTED)
            para(tf, val, 9.5, col, bold=last, first=True, line=1.2)
        x += w
    ty += rh
    if not last:
        rect(s, ML, ty - Inches(0.02), CW, Pt(0.6), HAIR)

footer(s, "Read from Google Play listings, company sites and FAQ pages, "
          "September 2026. Splitwise declined the same confirmation mechanic in "
          "2015 as “a hassle” — for splitting dinner bills. For a debt someone "
          "else recorded against your name, the calculation is different.",
       MUTED)

# ═══════════════════════════════════════════════════════════════════════════
# 10 · 3 OCTOBER
# ═══════════════════════════════════════════════════════════════════════════
s = slide()
eyebrow(s, "What runs on 3 October")
title(s, "Forty seconds, zero typing, and a loop that closes.")
standfirst(s, "Built inside the eight hours, on synthetic data that is labelled "
              "synthetic on every screen, and designed to keep working when the "
              "venue wifi does not.")
cards(s, [
    ("The demo", [
        "**1.** The shopkeeper speaks an entry to the Soundbox.",
        "**2.** A real phone on the judges’ table buzzes.",
        "**3.** A judge taps Confirm.",
        "**4.** Both ledgers update in front of them, inside one 2-second tick.",
        "**5.** “Do not chase Sharma before day 7 — he has paid on day 9 for "
        "two years. Four of thirty-eight get a message tomorrow.”",
        "No typing at any point. The judge holds one half of the product."]),
    ("What is real", [
        "The voice capture and the rule-based parse.",
        "The confirmation round-trip between two devices.",
        "The ledger, the state machine, and the dispute path.",
        "**The rhythm arithmetic** — median gap per customer, from that "
        "customer’s own settled history.",
        "The expiry rule, including refusing to prompt past the limitation "
        "line.",
        "**Every figure on every screen is computed from the data.** None is "
        "written into the copy."]),
    ("What is mocked, and labelled", [
        "One shop, 60 udhaar customers, six months of entries and repayments "
        "with believable per-person rhythms. Generated the night before, "
        "deterministically.",
        "No real UPI. No real Soundbox hardware — a browser microphone stands "
        "in, and we say so.",
        "No auth, no second shop.",
        "**Every screen carries a synthetic-data label.** We would rather "
        "declare it than be asked."]),
    ("How it survives the room", [
        "**Deployed publicly before the day**, so the judge’s phone reaches us "
        "over its own mobile data and never touches venue wifi.",
        "Every spoken line cached to disk. SARVAM_OFFLINE defaults on.",
        "**Frozen at hour five**, with a backup video recorded while it still "
        "works.",
        "**No hardcoded shortcuts.** Change a repayment date in the database "
        "and the reminder day moves. We will hand you the laptop and let you "
        "try it."]),
], body_size=9.5)

out = "docs/BAHI-Round1.pptx"
prs.save(out)
print("wrote", out, "·", len(prs.slides._sldIdLst), "slides")
