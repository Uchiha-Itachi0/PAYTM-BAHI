"""
BAHI — the final deck (after Round 1).

Sixteen slides, in the order the team asked for: the title, what Paytm gets,
the problem, the solution, cash by voice, nicknames and customers with no phone, the counter,
where AI works, what the customer and the shopkeeper each get, how easy it is to
ship and what it can earn, then impact and proof. Screens
are captured from the working app (docs/final/*.png, demo data).

Three rules drive it.

1. SKIMMED, NOT READ. 1,771 teams registered and the PDF alone decides the
   shortlist, so a reviewer gives each page seconds. Every slide makes one
   point, its title is that point as a sentence, and the body stays near 100
   words at 12pt or larger.

2. ONE PICTURE PER SLIDE. A flow, an architecture, phone screens or a table,
   drawn as native shapes so the PDF stays sharp and the file stays editable.

3. EVERY FACT IS SOURCED, AND ONLY USEFUL FACTS ARE KEPT. A number, a claim
   about another company or a statement of law carries its source on the same
   slide. Our own design is stated as design, our demo data is labelled as
   demo data, and anything we could not source was cut.

It should look like Paytm: pale sky ground, floating white cards, navy
headings, cyan as a rule or mark and never as text (#00BAF2 is ~2.0:1 on
white). Arial, because LibreOffice's PDF export silently swaps .ttc fonts
like Helvetica Neue for a serif.
"""

from __future__ import annotations

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn
from pptx.util import Inches as I, Pt

# ── Paytm palette ──────────────────────────────────────────────────────────
NAVY = RGBColor(0x00, 0x29, 0x70)
CYAN = RGBColor(0x00, 0xBA, 0xF2)
CYAN_TX = RGBColor(0x00, 0x77, 0xA8)
SKY = RGBColor(0xEA, 0xF6, 0xFC)
SKY_2 = RGBColor(0xD6, 0xEE, 0xF9)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
INK = RGBColor(0x1C, 0x1C, 0x1C)
MUTED = RGBColor(0x5B, 0x66, 0x75)
FAINT = RGBColor(0x8B, 0x95, 0xA5)
HAIR = RGBColor(0xD9, 0xE4, 0xEC)
GREEN = RGBColor(0x1E, 0x7E, 0x34)
RED = RGBColor(0xB3, 0x26, 0x1E)
PALE = RGBColor(0x8F, 0xA4, 0xC6)

F = "Arial"
LEFT, CENTER = PP_ALIGN.LEFT, PP_ALIGN.CENTER
MID = MSO_ANCHOR.MIDDLE

W, H = I(13.333), I(7.5)
ML = I(0.62)
CW = W - I(1.24)
TOP = I(1.80)          # where content starts under the title
BOTTOM = I(6.72)       # where content must end, above the footer

prs = Presentation()
prs.slide_width, prs.slide_height = W, H
BLANK = prs.slide_layouts[6]
TOTAL = 16


# ── primitives ─────────────────────────────────────────────────────────────
def flat(shape):
    """Drop the theme style python-pptx attaches, which LibreOffice renders as
    a drop shadow on every shape (and thickens every hairline)."""
    style = shape._element.find(qn("p:style"))
    if style is not None:
        shape._element.remove(style)
    return shape


def slide(bg=SKY):
    s = prs.slides.add_slide(BLANK)
    rect(s, 0, 0, W, H, bg)
    return s


def rect(s, x, y, w, h, color, shape=MSO_SHAPE.RECTANGLE, radius=None):
    r = s.shapes.add_shape(shape, x, y, w, h)
    r.fill.solid()
    r.fill.fore_color.rgb = color
    r.line.fill.background()
    flat(r)
    if radius is not None:
        r.adjustments[0] = radius
    return r


def card(s, x, y, w, h, color=WHITE, radius=0.06):
    return rect(s, x, y, w, h, color, MSO_SHAPE.ROUNDED_RECTANGLE, radius)


def tb(s, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    tf = s.shapes.add_textbox(x, y, w, h).text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    return tf


def para(tf, text, size, color=INK, bold=False, line=1.3, after=0, before=0,
         first=False, align=None, spc=None, link=None):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.line_spacing = line
    p.space_after = Pt(after)
    p.space_before = Pt(before)
    if align is not None:
        p.alignment = align
    r = p.add_run()
    r.text = text
    if link:
        r.hyperlink.address = link
    f = r.font
    f.size, f.name, f.bold = Pt(size), F, bold
    f.color.rgb = color
    if spc is not None:
        f._rPr.set("spc", str(int(spc * 100)))
    return p


def rich(tf, parts, size, first=False, line=1.3, after=0, before=0, align=None):
    """One paragraph of mixed runs: parts are (text, color, bold)."""
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.line_spacing = line
    p.space_after = Pt(after)
    p.space_before = Pt(before)
    if align is not None:
        p.alignment = align
    for text, color, bold in parts:
        r = p.add_run()
        r.text = text
        r.font.size, r.font.name, r.font.bold = Pt(size), F, bold
        r.font.color.rgb = color
    return p


def eyebrow(s, text):
    para(tb(s, ML, I(0.42), CW, I(0.25)), text.upper(), 10, CYAN_TX,
         bold=True, first=True, spc=1.4)


def title(s, text, size=26):
    para(tb(s, ML, I(0.74), CW, I(0.9)), text, size, NAVY, bold=True,
         first=True, line=1.05)


def footer(s, text=None):
    """Source line bottom-left, page number bottom-right."""
    n = len(prs.slides._sldIdLst)
    if text:
        para(tb(s, ML, I(6.98), CW - I(0.8), I(0.3)), text, 9, FAINT,
             first=True, line=1.2)
    para(tb(s, W - ML - I(0.7), I(6.98), I(0.7), I(0.3)), f"{n} / {TOTAL}",
         9, FAINT, first=True, align=PP_ALIGN.RIGHT)


def arrow(s, x1, y1, x2, y2, color=NAVY, width=2.0, dashed=False):
    c = flat(s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2))
    c.line.color.rgb = color
    c.line.width = Pt(width)
    if dashed:
        c.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    end = etree.SubElement(c.line._get_or_add_ln(), qn("a:tailEnd"))
    end.set("type", "triangle")
    end.set("w", "med")
    end.set("len", "med")
    return c


def num(s, x, y, n, d=I(0.36), fill=NAVY, color=WHITE, size=12):
    rect(s, x, y, d, d, fill, MSO_SHAPE.OVAL)
    para(tb(s, x, y, d, d, anchor=MID), str(n), size, color, bold=True,
         first=True, align=CENTER, line=1.0)


def pill(s, x, y, text, fill, color, w, h=I(0.26), size=9):
    rect(s, x, y, w, h, fill, MSO_SHAPE.ROUNDED_RECTANGLE, 0.5)
    para(tb(s, x, y, w, h, anchor=MID), text, size, color, bold=True,
         first=True, align=CENTER, line=1.0, spc=0.8)


def node(s, x, y, w, h, head, sub=None, fill=WHITE, head_color=NAVY,
         sub_color=MUTED, head_size=13, sub_size=11, outline=None, dashed=False):
    r = card(s, x, y, w, h, fill, 0.12)
    if outline is not None:
        r.line.color.rgb = outline
        r.line.width = Pt(1.25)
        if dashed:
            r.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    tf = tb(s, x + I(0.12), y, w - I(0.24), h, anchor=MID)
    para(tf, head, head_size, head_color, bold=True, first=True, align=CENTER,
         line=1.1)
    if sub:
        para(tf, sub, sub_size, sub_color, align=CENTER, line=1.2, before=3)


def phone(s, path, x, y, w, frame=True):
    """A screen from the app, its own ratio kept, in a thin phone edge."""
    from PIL import Image

    pw, ph = Image.open(path).size
    h = int(w * ph / pw)
    if frame:
        r = card(s, x - Pt(3), y - Pt(3), w + Pt(6), h + Pt(6), WHITE, 0.05)
        r.line.color.rgb = HAIR
        r.line.width = Pt(1)
    s.shapes.add_picture(path, x, y, width=w, height=h)
    return h


def cols(n, gutter, x=ML, width=CW):
    w = int((width - gutter * (n - 1)) / n)
    return [(x + i * (w + gutter), w) for i in range(n)]



# ═══════════════════════════════════════════════════════════════════════════
# 1 · TITLE
# ═══════════════════════════════════════════════════════════════════════════
s = slide(NAVY)
rect(s, 0, 0, W, Pt(8), CYAN)

# The result from the Mumbai panel, first thing a reader sees.
rect(s, ML, I(0.85), I(7.45), I(0.4), CYAN, MSO_SHAPE.ROUNDED_RECTANGLE, 0.5)
para(tb(s, ML, I(0.85), I(7.45), I(0.4), anchor=MID),
     "This idea was selected in the top 10 at the Paytm Build for India AI "
     "Hackathon, Mumbai", 12, NAVY, bold=True, first=True, align=CENTER, line=1.0)
tf = tb(s, ML, I(1.45), I(7.0), I(4.6))
para(tf, "BAHI", 70, WHITE, bold=True, first=True, line=0.95)
para(tf, "The khata both sides can see.", 28, WHITE, bold=True,
     before=10, line=1.1)
para(tf, "The customer scans the shop’s udhaar QR, or asks for udhaar on her "
         "own phone. The shopkeeper tells his AI munshi the amount, and nothing "
         "is written until both sides say yes. Every night, plain code decides "
         "who actually needs a reminder.",
     15, RGBColor(0xC9, 0xD8, 0xEE), before=18, line=1.4)
rect(s, ML, I(5.55), I(0.5), Pt(3), CYAN)
tf = tb(s, ML, I(5.75), I(7.3), I(0.8))
para(tf, "Paytm Build for India AI Hackathon  ·  Mumbai, 3 October 2026",
     12, WHITE, first=True)
para(tf, "Track 2: AI-Powered Financial Journeys", 12, WHITE, before=4)
para(tf, "Team Hustlers  ·  picked by the Paytm panel as a top 10 project", 12,
     PALE, before=10)

phone(s, "docs/final/m-popup.png", I(8.3), I(1.0), I(2.2))
phone(s, "docs/final/c-chat.png", I(10.75), I(1.0), I(2.2))
para(tb(s, I(8.3), I(5.62), I(4.65), I(0.3)),
     "Shopkeeper  ·  Customer  ·  our working app, demo data",
     10, PALE, first=True, align=CENTER)

# ═══════════════════════════════════════════════════════════════════════════
# 2 · WHAT PAYTM GETS
# ═══════════════════════════════════════════════════════════════════════════
s = slide()
eyebrow(s, "What Paytm gets")
title(s, "More revenue from merchants and customers Paytm already has.")

LW = I(4.1)
card(s, ML, TOP, LW, BOTTOM - TOP, NAVY)
tf = tb(s, ML + I(0.35), TOP + I(0.4), LW - I(0.7), I(4.2))
para(tf, "₹9", 60, WHITE, bold=True, first=True, line=1.0)
para(tf, "a month, added to the Soundbox plan the merchant already pays.", 16,
     WHITE, bold=True, before=12, line=1.3)
para(tf, "The customer pays nothing. There is no new device to ship and no new "
         "app to install.", 13, RGBColor(0xC9, 0xD8, 0xEE), before=14, line=1.4)
para(tb(s, ML + I(0.35), BOTTOM - I(0.75), LW - I(0.7), I(0.6)),
     "Our proposed price. The numbers behind it are on slide 14.", 10, PALE,
     first=True, line=1.3)

RX = ML + LW + I(0.3)
RW = CW - LW - I(0.3)
gets = [
    ("Customer acquisition is already done",
     "1.57 Cr storefronts run a Paytm Soundbox, and their customers pay with "
     "Paytm. BAHI is sold to people Paytm has already won."),
    ("Paytm Business Khata, made two-sided",
     "Business Khata already keeps the shop’s udhaar. BAHI adds the customer’s "
     "own copy, the AI munshi and the Soundbox voice."),
    ("Udhaar moves from cash to Paytm UPI",
     "Every repayment is a tap in the customer’s chat with the shop, paid by "
     "Paytm UPI."),
]
GH = int((BOTTOM - TOP - I(0.24)) / 3)
for k, (head, body) in enumerate(gets):
    y = TOP + k * (GH + I(0.12))
    card(s, RX, y, RW, GH)
    num(s, RX + I(0.3), y + (GH - I(0.42)) // 2, k + 1, I(0.42), size=14)
    tf = tb(s, RX + I(0.95), y, RW - I(1.25), GH, anchor=MID)
    para(tf, head, 16, NAVY, bold=True, first=True, line=1.15)
    para(tf, body, 12.5, MUTED, before=5, line=1.35)
footer(s, "Sources: Paytm Q1 FY27 earnings release (1.57 Cr Soundbox storefronts); "
          "business.paytm.com/business-khata, checked 23 Sep 2026.")

# ═══════════════════════════════════════════════════════════════════════════
# 3 · PROBLEM
# ═══════════════════════════════════════════════════════════════════════════
s = slide()
eyebrow(s, "The problem")
title(s, "The udhaar book has one author. The customer never sees it.")

card(s, ML, TOP, CW, I(2.05))
ny, nh, nw = I(2.20), I(1.25), I(2.7)
xs = [ML + I(0.45), ML + I(4.69), ML + I(8.94)]
node(s, xs[0], ny, nw, nh, "Shopkeeper", "writes every entry", fill=SKY,
     head_size=15, sub_size=12)
node(s, xs[1], ny, nw, nh, "The udhaar book", "a notebook, or a ledger app",
     fill=SKY, head_size=15, sub_size=12)
node(s, xs[2], ny, nw, nh, "Customer", "no copy  ·  no total  ·  no proof",
     fill=WHITE, head_color=MUTED, outline=FAINT, dashed=True, head_size=15,
     sub_size=12)
ay = ny + nh // 2
arrow(s, xs[0] + nw + I(0.1), ay, xs[1] - I(0.1), ay)
arrow(s, xs[1] + nw + I(0.1), ay, xs[2] - I(0.1), ay, FAINT, dashed=True)
para(tb(s, xs[0] + nw, ay - I(0.36), xs[1] - xs[0] - nw, I(0.3)), "writes",
     11, NAVY, bold=True, first=True, align=CENTER)
para(tb(s, xs[1] + nw, ay - I(0.36), xs[2] - xs[1] - nw, I(0.3)),
     "an SMS, at best", 11, MUTED, first=True, align=CENTER)

points = [
    ("He can’t see patterns",
     "Someone who always pays on day 9 and someone quietly drifting away look "
     "the same in a notebook. So everyone is chased the same way."),
    ("The customer has no record",
     "He can’t see what he owes across shops. If the book says ₹500 and he "
     "remembers ₹300, he has nothing to show."),
    ("Apps went digital on one side only",
     "Khatabook alone has 5 Cr+ downloads. Its customers still get only an SMS "
     "— no app of their own, and no say in the entry."),
]
for (x, w), (head, body) in zip(cols(3, I(0.4)), points):
    rect(s, x, I(4.28), I(0.4), Pt(3), CYAN)
    tf = tb(s, x, I(4.45), w, I(2.2))
    para(tf, head, 16, NAVY, bold=True, first=True, line=1.15)
    para(tf, body, 13, MUTED, before=8, line=1.4)
footer(s, "Source: Khatabook on Google Play (5 Cr+ downloads) and khatabook.com, "
          "checked 23 Sep 2026.")


# ═══════════════════════════════════════════════════════════════════════════
# 4 · SOLUTION
# ═══════════════════════════════════════════════════════════════════════════
s = slide()
eyebrow(s, "The solution")
title(s, "One entry, agreed by both sides, inside the Paytm they already use.")

steps = [
    ("docs/final/c-ask.png", "She scans, and can ask",
     "A separate udhaar QR. She may say how much, and what for."),
    ("docs/final/m-popup.png", "The shop says yes",
     "Or says the amount to the munshi. Nothing is written before his yes."),
    ("docs/final/c-agreed.png", "In both books",
     "Her ask was her yes. Otherwise: “Yes, I owe ₹200” on her phone."),
    ("docs/final/c-chat.png", "A chat like a passbook",
     "Every udhaar and payment shows the total before and after it."),
    ("docs/final/m-tonight.png", "Code picks who hears",
     "Only people past their own longest gap. Everyone else is held, with why."),
]
PW = I(1.62)
for i, ((x, w), (path, head, body)) in enumerate(zip(cols(5, I(0.2)), steps)):
    phone(s, path, x + (w - PW) // 2, I(1.62), PW)
    num(s, x + I(0.04), I(5.0), i + 1, I(0.32), size=11)
    tf = tb(s, x + I(0.44), I(5.0), w - I(0.44), I(1.6))
    para(tf, head, 13, NAVY, bold=True, first=True, line=1.1)
    para(tf, body, 11.5, MUTED, before=4, line=1.3)
footer(s, "Screens captured from our working app. Names and amounts are demo data.")


# ═══════════════════════════════════════════════════════════════════════════
# 5, 6 · CASH BY VOICE; NICKNAMES, NO PHONE, NO CASH
# ═══════════════════════════════════════════════════════════════════════════
def three_screens(eyebrow_text, title_text, items, note):
    s = slide()
    eyebrow(s, eyebrow_text)
    title(s, title_text)
    PW = I(1.72)
    for i, ((x, w), (path, head, body)) in enumerate(zip(cols(3, I(0.4)), items)):
        phone(s, path, x + I(0.05), I(1.62), PW)
        tx = x + PW + I(0.4)
        tw = w - PW - I(0.4)
        num(s, tx, I(1.7), i + 1, I(0.4), size=13)
        tf = tb(s, tx, I(2.3), tw, I(3.6))
        para(tf, head, 16, NAVY, bold=True, first=True, line=1.15)
        para(tf, body, 12.5, MUTED, before=8, line=1.4)
    footer(s, note)


three_screens(
    "The solution / paid in cash",
    "Paid in cash? He says so, and that udhaar is gone.",
    [("docs/final/m-cash-card.png", "He says it",
      "“Sharma ne 200 cash diye.” The munshi finds Sharma and puts up a जमा "
      "card for ₹200."),
     ("docs/final/m-cash-done.png", "His yes writes it",
      "The cash clears Sharma’s oldest open udhaar first. The munshi says it "
      "is written and sent."),
     ("docs/final/c-cash-chat.png", "Gone on both sides",
      "Sharma’s own chat shows “Paid in cash”, and his udhaar goes from ₹200 "
      "to nothing left.")],
    "Screens from our working app, with the munshi live on Sarvam. Only money "
    "the customer handed over is जमा; a mistake is taken back, never cleared "
    "with a जमा.",
)

three_screens(
    "The solution / more that a notebook can’t do",
    "Nicknames, customers with no phone, and paying without cash.",
    [("docs/final/m-nickname.png", "Nicknames",
      "He says “Golu”. The munshi asks who that is, and remembers. Next time, "
      "“Golu” finds Sharma straight away."),
     ("docs/final/m-nameonly.png", "No phone needed",
      "A customer with no phone is kept by name, like the notebook. Add their "
      "number later and every open entry goes to them for a yes."),
     ("docs/final/c-pay.png", "Cashless",
      "The customer pays from her chat by UPI, all of it or part. The shop is "
      "told what is left.")],
    "Screens captured from our working app. Names and amounts are demo data.",
)


three_screens(
    "The solution / the counter",
    "Scan the udhaar QR, and you’re at the counter, first in line.",
    [("docs/final/c-counter.png", "She scans",
      "The udhaar QR puts her on the shop’s counter list for three minutes. Her "
      "phone tells her the shop can see her."),
     ("docs/final/m-counter.png", "Top of his screen",
      "People at the counter come first. With one there, she is already "
      "picked: he says or types ₹200 and sends."),
     ("docs/final/c-counter-yes.png", "Her yes, on the spot",
      "Her phone asks “Yes, I owe ₹200” at once, before she leaves the "
      "counter.")],
    "When he says a name, people at the counter are checked first: “Ganesh ko "
    "do sau” goes to the Ganesh standing there. With two or more there, nobody "
    "is picked until he taps one.",
)


# ═══════════════════════════════════════════════════════════════════════════
# 7 · WHERE AI WORKS
# ═══════════════════════════════════════════════════════════════════════════
s = slide()
eyebrow(s, "AI in BAHI")
title(s, "Five jobs for AI: hear, understand, speak, remember, predict.")

COLW = [I(1.75), I(2.45), I(4.75), I(3.14)]
HEADS = ["The job", "Model", "What it does", "Where you see it"]
ROWS = [
    ("Hear", "Sarvam Saaras v4",
     "Speech to text in whatever language is spoken, with the shop’s customer "
     "names as hints.",
     "Add udhaar by voice, the munshi"),
    ("Understand", "Sarvam-105B",
     "The munshi: works out what he meant and calls our tools to find a "
     "customer, put an entry on a card or look something up.",
     "Paytm Assistant, voice entries"),
    ("Speak", "Sarvam Bulbul v3",
     "Says amounts on the Soundbox and reads the munshi’s replies aloud.",
     "Soundbox, Assistant"),
    ("Remember", "Cognee + pgvector",
     "Turns notes, promises and nicknames into a knowledge graph per shop, "
     "and recalls them by meaning.",
     "“Salary on the 7th”, “Pappu is Prakash”"),
    ("Predict", "Pattern engine + Sarvam-105B",
     "When each customer will likely pay, and who is drifting. The munshi "
     "says it as a guess.",
     "Customer card, Tomorrow, “इस हफ़्ते कौन देगा?”"),
]
y = TOP - I(0.05)
x = ML
for w, head in zip(COLW, HEADS):
    para(tb(s, x, y, w, I(0.3)), head.upper(), 9.5, CYAN_TX, bold=True,
         first=True, spc=1.0)
    x += w
y += I(0.32)
rect(s, ML, y, CW, Pt(1.5), CYAN)
y += I(0.06)
RH = I(0.88)
for r, cells in enumerate(ROWS):
    card(s, ML - I(0.08), y + I(0.04), CW + I(0.16), RH - I(0.08), WHITE, 0.12)
    x = ML
    for c, (w, val) in enumerate(zip(COLW, cells)):
        tf = tb(s, x + I(0.1), y, w - I(0.25), RH, anchor=MID)
        if c == 0:
            para(tf, val, 16, NAVY, bold=True, first=True)
        elif c == 1:
            para(tf, val, 12.5, NAVY, bold=True, first=True, line=1.2)
        else:
            para(tf, val, 12 if c == 2 else 11.5, INK if c == 2 else MUTED,
                 first=True, line=1.3)
        x += w
    y += RH
footer(s, "Prediction is arithmetic on the customer’s own ledger, so every figure "
          "can be checked by hand; no model ever produces a number. Cognee runs in "
          "our local build and is off in the hosted demo.")


# ═══════════════════════════════════════════════════════════════════════════
# 8 · THE MUNSHI
# ═══════════════════════════════════════════════════════════════════════════
s = slide()
eyebrow(s, "AI in BAHI / the munshi")
title(s, "An AI munshi that does the work, and never writes without a yes.")

PW = I(2.05)
phone(s, "docs/final/m-assistant.png", ML + I(0.05), TOP, PW)
phone(s, "docs/final/m-chat.png", ML + PW + I(0.35), TOP, PW)

RX = ML + 2 * PW + I(0.75)
RW = CW - (RX - ML)
card(s, RX, TOP, RW, I(3.3))
tf = tb(s, RX + I(0.3), TOP + I(0.25), RW - I(0.6), I(3.0))
para(tf, "What it does", 15, NAVY, bold=True, first=True, after=2)
for ln in [
    "Talk or type, in Hindi, English, Marathi or a mix. Sarvam hears any of them.",
    "Finds the customer by the sound of a name, or how the shop describes them.",
    "Asks before reading names; then says only the names.",
    "Puts every change on a card: an entry, a payment, a correction, taking "
    "one back, new details, a message. Only his yes writes it.",
    "Paytm Assistant: ask anything about the book. The chat is kept.",
]:
    rich(tf, [("—  ", CYAN_TX, True), (ln, INK, False)], 12.5, before=7,
         line=1.3)

card(s, RX, TOP + I(3.5), RW, BOTTOM - TOP - I(3.5), NAVY)
tf = tb(s, RX + I(0.3), TOP + I(3.68), RW - I(0.6), I(1.3))
para(tf, "Its tools are our code", 14, WHITE, bold=True, first=True)
para(tf, "find_customer  ·  counter  ·  customer_card  ·  propose_entry  ·  "
         "propose_correction  ·  propose_removal  ·  propose_details  ·  "
         "propose_message  ·  remember  ·  recall  ·  expected_payments  ·  tonight",
     11, RGBColor(0xC9, 0xD8, 0xEE), before=6, line=1.35)
footer(s, "Replies shown are from our live test with Sarvam. An ordinary card goes "
          "in 3 s unless he says no; a close-sounding name, ₹5,000+ or 3× his usual "
          "waits for a clear हाँ.")


# ═══════════════════════════════════════════════════════════════════════════
# 9, 10 · WHAT EACH SIDE GETS
# ═══════════════════════════════════════════════════════════════════════════
def features(eyebrow_text, title_text, shots, head, lines, note):
    s = slide()
    eyebrow(s, eyebrow_text)
    title(s, title_text)
    PW = I(1.62)
    gap = I(0.22)
    for k, path in enumerate(shots):
        phone(s, path, ML + I(0.05) + k * (PW + gap), TOP, PW)
    para(tb(s, ML, TOP + I(3.32), 3 * PW + 2 * gap, I(0.3)), note, 10, MUTED,
         first=True, align=CENTER)
    RX = ML + 3 * PW + 2 * gap + I(0.45)
    RW = CW - (RX - ML)
    card(s, RX, TOP, RW, BOTTOM - TOP)
    tf = tb(s, RX + I(0.35), TOP + I(0.3), RW - I(0.7), BOTTOM - TOP - I(0.5))
    para(tf, head, 16, NAVY, bold=True, first=True, after=2)
    for ln in lines:
        rich(tf, [("—  ", CYAN_TX, True), (ln, INK, False)], 13, before=9,
             line=1.3)
    footer(s, "Screens captured from our working app. Names and amounts are "
              "demo data.")


features(
    "For the customer",
    "Her own copy of every udhaar, inside the Paytm app she already has.",
    ["docs/final/c-ask.png", "docs/final/c-agreed.png", "docs/final/c-mybook.png"],
    "What the customer can do",
    ["Scan the shop’s udhaar QR. Nothing to download: it is Paytm.",
     "Ask for udhaar herself: how much, and what for.",
     "Say yes to each entry, or tap “Not mine” or “Wrong amount”.",
     "A chat with each shop that reads like a passbook: the total before and "
     "after every entry.",
     "See what she owes across every shop, and pay by UPI, all or part.",
     "Reminders come privately, in her language, with no due date and no "
     "interest."],
    "Ask  ·  Agreed  ·  My udhaar",
)

features(
    "For the shopkeeper",
    "He says it once. The munshi, the Soundbox and the code do the rest.",
    ["docs/final/m-home.png", "docs/final/m-popup.png", "docs/final/m-tonight.png"],
    "What the shopkeeper can do",
    ["Say the amount to the munshi in any language, or tap the keypad.",
     "A customer’s ask pops up on his screen: Yes, No or Change amount.",
     "The Soundbox says the amount aloud, and never a name.",
     "Correct an entry or take it back, in the open.",
     "Ask anything: “कितना बाकी है?”, “इस हफ़्ते कौन देगा?”",
     "BAHI remembers promises and notes, and holds a reminder for them.",
     "Only people late by their own pattern get a reminder. He can rewrite, "
     "move, stop or pause it."],
    "Home  ·  A customer asks  ·  Tomorrow",
)


# ═══════════════════════════════════════════════════════════════════════════
# 11 · TECH
# ═══════════════════════════════════════════════════════════════════════════
s = slide()
eyebrow(s, "Technology")
title(s, "AI understands the words. Plain code decides every number.")


def tagged(s, x, y, w, h, head, sub, tag=None):
    node(s, x, y, w, h, head, sub, head_size=13, sub_size=11)
    if tag == "AI":
        pill(s, x + I(0.14), y - I(0.13), "AI", CYAN, NAVY, I(0.46))
    elif tag == "CODE":
        pill(s, x + I(0.14), y - I(0.13), "CODE", NAVY, WHITE, I(0.66))


def row(s, y, label, items):
    para(tb(s, ML, y - I(0.40), CW, I(0.25)), label.upper(), 9.5, MUTED,
         bold=True, first=True, spc=1.2)
    n = len(items)
    gap = I(0.52)
    w = int((CW - gap * (n - 1)) / n)
    h = I(1.05)
    for i, (head, sub, tag) in enumerate(items):
        x = ML + i * (w + gap)
        tagged(s, x, y, w, h, head, sub, tag)
        if i < n - 1:
            arrow(s, x + w + I(0.07), y + h // 2, x + w + gap - I(0.07),
                  y + h // 2, width=1.75)


row(s, I(2.12), "During the day — recording an entry", [
    ("Shopkeeper speaks", "“Kavita ko do sau”", None),
    ("Sarvam Saaras v4", "speech → text, any language", "AI"),
    ("The munshi", "Sarvam-105B calls our tools", "AI"),
    ("Our checks", "finds by sound; the rupees match the words", "CODE"),
    ("Two yeses", "his, then hers, then the ledger", None),
])
row(s, I(3.95), "Every night — deciding who hears from us", [
    ("Timing engine", "each customer’s own longest gap", "CODE"),
    ("What was said", "a promise or a note holds it", "CODE"),
    ("The munshi writes", "the words, in her language", "AI"),
    ("Our check", "the only figure is her balance", "CODE"),
])

card(s, ML, I(5.35), CW, I(0.78))
tf = tb(s, ML + I(0.25), I(5.35), CW - I(0.5), I(0.78), anchor=MID)
rich(tf, [("How we prove it:  ", NAVY, True),
          ("a test fails the build if the core logic imports anything outside "
           "Python’s standard library. The model only ever returns words.",
           INK, False)],
     13, first=True)

stack = ["Next.js 16", "React 19", "FastAPI", "Python 3.13", "PostgreSQL",
         "Sarvam Saaras", "Sarvam-105B", "Bulbul v3", "Cognee",
         "Vercel · Render · Supabase"]
x = ML
para(tb(s, x, I(6.36), I(0.8), I(0.3), anchor=MID), "STACK", 9.5, MUTED,
     bold=True, first=True, spc=1.2)
x += I(0.8)
for name in stack:
    w = I(0.22 + 0.075 * len(name))
    pill(s, x, I(6.36), name, WHITE, NAVY, w, I(0.3), size=9.5)
    x += w + I(0.08)
footer(s)

# ═══════════════════════════════════════════════════════════════════════════
# 12 · USP
# ═══════════════════════════════════════════════════════════════════════════
s = slide()
eyebrow(s, "Unique selling proposition")
title(s, "Every udhaar app serves the shopkeeper. We add the customer.")

COLW = [I(3.0), I(2.6), I(3.35), I(3.14)]
HEADS = ["", "Downloads", "Customer has an app", "Customer confirms entries"]
ROWS = [
    ("Khatabook", "5 Cr+", "No — SMS / WhatsApp", "No"),
    ("OkCredit", "1 Cr+", "No — “They don’t need the app”", "No"),
    ("Paytm Business Khata", "Inside Paytm for Business",
     "No — SMS with a pay link", "No"),
    ("BAHI", "—", "Yes — inside the Paytm app", "Yes — one tap"),
]
y = TOP
x = ML
for w, head in zip(COLW, HEADS):
    para(tb(s, x, y, w, I(0.3)), head.upper(), 9.5, CYAN_TX, bold=True,
         first=True, spc=1.0)
    x += w
y += I(0.34)
rect(s, ML, y, CW, Pt(1.5), CYAN)
y += I(0.08)
RH = I(0.5)
for r, cells in enumerate(ROWS):
    ours = r == len(ROWS) - 1
    if ours:
        card(s, ML - I(0.1), y, CW + I(0.2), RH, WHITE, 0.2)
    x = ML
    for c, (w, val) in enumerate(zip(COLW, cells)):
        tf = tb(s, x + (I(0.02) if c else 0), y, w - I(0.1), RH, anchor=MID)
        if c == 0:
            para(tf, val, 14, NAVY if ours else INK, bold=True, first=True)
        elif c == 1:
            para(tf, val, 12.5, MUTED, first=True, bold=ours)
        else:
            color = GREEN if val.startswith("Yes") else RED
            para(tf, val, 12.5, color, first=True, bold=ours)
        x += w
    y += RH
    if not ours:
        rect(s, ML, y - Pt(0.5), CW, Pt(0.75), HAIR)

usps = [
    ("Two-sided", "An entry becomes a fact only when the customer confirms it."),
    ("Scan, then speak", "The QR says who, his voice says how much. Nothing to type."),
    ("Timed per person",
     "Reminders follow each customer’s own repayment pattern."),
]
for (x, w), (head, body) in zip(cols(3, I(0.3)), usps):
    card(s, x, I(5.05), w, I(1.55))
    rect(s, x + I(0.25), I(5.28), I(0.4), Pt(3), CYAN)
    tf = tb(s, x + I(0.25), I(5.42), w - I(0.5), I(1.1))
    para(tf, head, 15, NAVY, bold=True, first=True)
    para(tf, body, 12.5, MUTED, before=5, line=1.35)
footer(s, "Sources: Google Play listings, okcredit.in, khatabook.com and "
          "business.paytm.com, checked 23 Sep 2026.")

# ═══════════════════════════════════════════════════════════════════════════
# 13 · EASY TO SHIP, AND WHAT IT EARNS
# ═══════════════════════════════════════════════════════════════════════════
s = slide()
eyebrow(s, "Business model")
title(s, "No new hardware, and ₹9 more a month from each merchant.")

LW = I(5.0)
card(s, ML, TOP, LW, BOTTOM - TOP)
tf = tb(s, ML + I(0.35), TOP + I(0.3), LW - I(0.7), BOTTOM - TOP - I(0.5))
para(tf, "Easy to build and sell", 16, NAVY, bold=True, first=True, after=2)
for ln in [
    "Software only. No new hardware: the Soundbox already says amounts aloud.",
    "Built on what Paytm has: the Paytm app, its chats, UPI, the Soundbox and "
    "Business Khata.",
    "Sold as an add-on line on the merchant’s existing Soundbox bill, through "
    "the Paytm for Business app and the field team.",
    "A standalone ledger app lost ₹116 Cr in FY24 (Khatabook). BAHI needs no "
    "app of its own and no new customers.",
    "We built it working, end to end, during the hackathon.",
]:
    rich(tf, [("—  ", CYAN_TX, True), (ln, INK, False)], 12.5, before=9,
         line=1.3)

RX = ML + LW + I(0.3)
RW = CW - LW - I(0.3)
card(s, RX, TOP, RW, I(1.55), NAVY)
tf = tb(s, RX + I(0.35), TOP, RW - I(0.7), I(1.55), anchor=MID)
rich(tf, [("₹90  →  ₹99", WHITE, True)], 34, first=True, line=1.0)
para(tf, "a month from the same merchant, with no hardware delivered. Paytm’s "
         "Soundbox plan earned about ₹90 a device a month in Q4 FY24.", 12,
     RGBColor(0xC9, 0xD8, 0xEE), before=8, line=1.35)

ty = TOP + I(1.75)
card(s, RX, ty, RW, BOTTOM - ty)
tf = tb(s, RX + I(0.35), ty + I(0.22), RW - I(0.7), I(0.6))
para(tf, "Our guesstimate: merchants who add BAHI", 14, NAVY, bold=True,
     first=True)
para(tf, "Out of 1.24 Cr merchants paying for a Paytm device, at ₹9 a month.",
     11, MUTED, before=3)
TC = [I(1.9), I(2.0), RW - I(0.7) - I(3.9)]
rows = [("Take-up", "Merchants", "New revenue a year"),
        ("5%", "6.2 lakh", "₹6.7 Cr"),
        ("10%", "12.4 lakh", "₹13.4 Cr"),
        ("25%", "31 lakh", "₹33.5 Cr")]
yy = ty + I(1.0)
for r, cells in enumerate(rows):
    x = RX + I(0.35)
    for c, (w, val) in enumerate(zip(TC, cells)):
        para(tb(s, x, yy, w, I(0.4), anchor=MID), val.upper() if r == 0 else val,
             9.5 if r == 0 else 15, CYAN_TX if r == 0 else (NAVY if c == 2 else INK),
             bold=(r == 0 or c == 2), first=True, spc=1.0 if r == 0 else None)
        x += w
    yy += I(0.42) if r else I(0.36)
    rect(s, RX + I(0.35), yy - Pt(1), RW - I(0.7), Pt(0.75) if r else Pt(1.5),
         HAIR if r else CYAN)
para(tb(s, RX + I(0.35), BOTTOM - I(0.48), RW - I(0.7), I(0.35)),
     "Not counted: udhaar repayments moving from cash to Paytm UPI.", 10.5,
     MUTED, first=True)
footer(s, "Our estimate, not a forecast. ₹90/device/month: Paytm, Q4 FY24 "
          "(Business Standard, May 2024). 1.24 Cr device subscribers: Paytm FY25 "
          "Annual Report.")


# ═══════════════════════════════════════════════════════════════════════════
# 14 · IMPACT
# ═══════════════════════════════════════════════════════════════════════════
s = slide()
eyebrow(s, "Impact")
title(s, "Fewer reminders, sent only to people who are actually late.")

LW = I(3.75)
card(s, ML, TOP, LW, I(4.85), NAVY)
tf = tb(s, ML + I(0.35), TOP + I(0.45), LW - I(0.7), I(4.2))
para(tf, "4 of 38", 54, WHITE, bold=True, first=True, line=1.0)
para(tf, "customers who owe get a reminder tonight.", 15, WHITE, bold=True,
     before=14, line=1.3)
para(tf, "The other 34 are not late by their own pattern, so they hear "
         "nothing.", 13, RGBColor(0xC9, 0xD8, 0xEE), before=12, line=1.4)
para(tb(s, ML + I(0.35), TOP + I(4.2), LW - I(0.7), I(0.5)),
     "Our demo shop: 60 customers, six months of synthetic data.", 10, PALE,
     first=True, line=1.3)

who = [
    ("For the shopkeeper", ["Stops chasing people who always pay.",
                            "Spots the ones who are drifting.",
                            "Records by voice, so the queue keeps moving."]),
    ("For the customer", ["Sees his total across every shop.",
                          "Has proof of every entry.",
                          "Is reminded privately, not at the counter."]),
    ("For Paytm", ["Udhaar settled in cash moves to UPI.",
                   "A daily reason to use the Soundbox.",
                   "A new reason to open the Paytm app."]),
]
for (x, w), (head, lines) in zip(cols(3, I(0.26), ML + LW + I(0.3),
                                      CW - LW - I(0.3)), who):
    card(s, x, TOP, w, I(4.85))
    rect(s, x + I(0.25), TOP + I(0.28), I(0.4), Pt(3), CYAN)
    tf = tb(s, x + I(0.25), TOP + I(0.45), w - I(0.5), I(4.2))
    para(tf, head, 15, NAVY, bold=True, first=True, after=6)
    for ln in lines:
        para(tf, ln, 13, INK, before=12, line=1.35)
footer(s, "These are the outcomes we expect; a pilot would measure them. "
          "“4 of 38” is computed from our synthetic demo shop.")

# ═══════════════════════════════════════════════════════════════════════════
# 15 · PROOF
# ═══════════════════════════════════════════════════════════════════════════
s = slide()
eyebrow(s, "Proof")
title(s, "We tested the voice on 1,338 recordings. It gets it right, or it asks.")

LW = I(5.2)
card(s, ML, TOP, LW, BOTTOM - TOP)
tf = tb(s, ML + I(0.35), TOP + I(0.3), LW - I(0.7), BOTTOM - TOP - I(0.5))
para(tf, "How we made the 1,338 recordings", 16, NAVY, bold=True, first=True,
     after=2)
for ln in [
    "We wrote 42 things a shopkeeper says, like “Sharma ko do sau” or "
    "“B wing wale Kamat ne 300 diye”.",
    "12 voices spoke them: 10 Sarvam voices and 2 Mac voices.",
    "Each was played three ways: in a quiet shop, over street noise, and with "
    "a second customer talking.",
    "The test book had 68 customers, 20 of them named Anubhav, so picking the "
    "right person was hard.",
    "Every recording went through the app’s own path: Sarvam turned it into "
    "text, and our checks decided the entry.",
]:
    rich(tf, [("—  ", CYAN_TX, True), (ln, INK, False)], 12.5, before=9,
         line=1.3)

RX = ML + LW + I(0.3)
RW = CW - LW - I(0.3)
results = [
    ("73%", "right the first time", "The right person and amount, from the "
                                    "words alone.", NAVY),
    ("17%", "one tap", "Two people fit, so it asks “Kaunse Anubhav?” and he "
                       "taps the right one.", NAVY),
    ("8%", "said again", "It wasn’t sure, so it asked him to repeat it.", NAVY),
    ("2%", "wrong", "And even then, the customer still has to say yes on her "
                    "phone before it counts.", RED),
]
RH = int((BOTTOM - TOP - I(0.36)) / 4)
for k, (big, label, body, color) in enumerate(results):
    y = TOP + k * (RH + I(0.12))
    card(s, RX, y, RW, RH)
    para(tb(s, RX + I(0.3), y, I(1.3), RH, anchor=MID), big, 30, color,
         bold=True, first=True)
    tf = tb(s, RX + I(1.65), y, RW - I(1.95), RH, anchor=MID)
    para(tf, label, 14, color, bold=True, first=True)
    para(tf, body, 12, MUTED, before=3, line=1.3)
footer(s, "Run again any time with make voice-eval. Code: "
          "github.com/Uchiha-Itachi0/PAYTM-BAHI")


# Links in the theme are pure blue and purple; make them Paytm's text cyan.
theme = prs.slide_masters[0].part.part_related_by(RT.THEME)
theme._blob = (theme.blob
               .replace(b'<a:hlink><a:srgbClr val="0000FF"/>',
                        b'<a:hlink><a:srgbClr val="0077A8"/>')
               .replace(b'<a:folHlink><a:srgbClr val="800080"/>',
                        b'<a:folHlink><a:srgbClr val="0077A8"/>'))

out = "docs/BAHI-Final.pptx"
prs.save(out)
print("wrote", out, "·", len(prs.slides._sldIdLst), "slides")
