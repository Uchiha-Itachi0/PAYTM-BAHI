# Family circle (first version)

A family circle is a group of people who can pay each other's udhaar, at any
shop. One person makes it from phone numbers. When someone in it takes udhaar,
the bill can go on the circle's list, and anyone in the circle can pay it by UPI.

This is a first version built to be shown. The captain chose the behaviour
below, and some of it goes against what the research recommended
(`bahi-family-circle-research/report.md`, "Family Circle: the design"). Those
choices are marked here so they are easy to find and change.

## What it does

- **Make a circle.** A name and the members' mobile numbers (`/c/circle/new`).
  Each number must belong to a Paytm account (`paytm.by_phone`). The number only
  finds the account and is never stored. The maker is in the circle too, and
  everyone added gets a note on their phone. One person can be in many circles.
- **Add member.** Anyone in a circle can add one more person from the circle
  screen (`POST /circles/{c}/members`, by mobile number). The rules are the same
  as when making it: the number must belong to a Paytm account and is not kept,
  nobody is in the circle twice, and a circle holds at most `MOST_MEMBERS`. The
  new member gets the same "added" note. Their own setting, or the default,
  decides where their next udhaar goes; nothing they already owe is put on the
  list for them. Someone who left can be added back (a new membership row).
- **When I take udhaar.** Each person has a setting: *Send to my circle* or *Keep
  it to myself*. If they have never chosen, `DEFAULT_ON_UDHAAR` in
  `api/bahi/domain/circle.py` applies. It is set to `"circle"` because the
  captain asked for that.
- **After "Yes, I owe".** `ledger.confirm` (and the shop's yes to a customer's
  ask) calls `circle.on_agreed`. The route comes from `domain.circle.route`:
  - in one circle, with the setting on circle: the bill goes on that circle's
    list. The debtor gets a note (with **Take it back**), and every other member
    gets a "Pay it for them?" note;
  - in several circles: a note asks which one, and **Add to circle** opens a
    picker;
  - setting on self: a note offers **Pay it myself** or **Add to circle**;
  - in no circle: nothing happens.
- **Add to circle.** "Ask my family" is now **Add to circle**. In *My udhaar*,
  any agreed entry that still has something left to pay can be added by hand. An
  entry is on at most one list at a time.
- **Paying.** Any member can pay all or part of an open bill on the list
  (`POST /circles/{c}/entries/{e}/pay`, screen `/c/circle/{c}/pay/{e}`). It uses
  the same amount and UPI PIN steps as the usual pay screen, and they share
  `UpiPin`. The payment is a normal `repayments` row against the debtor's own
  entry, with `paid_by` set to the member who paid. Concurrent payments are
  serialised by a row lock, so a second payer can only pay what is left.
- **Notes follow the entry.** A note that asks for something about an udhaar
  (`help`, `shared`, `choose`, `kept`) is checked against the entry each time it
  is read (`domain.circle.notice_stands`). Its amount is what is left now, and it
  stops showing once the entry is paid, closed, or off that list, whoever paid
  it and however (a member, the debtor at the shop, or cash in the book).
- **Leaving.** `POST /circles/{c}/leave` takes all of the leaver's bills off the
  list straight away (`withdrawn_why = 'left'`) and closes the notes about them.
  The debt stays theirs. From then on only they can pay it, through the usual
  pay flow.
- **Seed.** `make db` creates the Sharma family: Rakesh, Sunita and Rohan.
  Rakesh's agreed udhaar at Ramesh Kirana and at Salim's is already on the list.
  His bill at Gupta's is not, so Add to circle can be tried live. Sunita
  (9819019020) and Rohan (9819019021) are Paytm accounts with no shop book of
  their own.

## The rules it keeps

| Rule | Where it is enforced |
|---|---|
| The person who said yes stays the debtor; members can pay but never owe | `repayments.paid_by` is the only new money column, and the payment still names the debtor's entry. There is no table that records one member owing another. |
| Only an agreed entry goes on a list | Trigger `circle_shares_agreed_only`, plus `circle.is_open` |
| No amount on circle rows, so nothing can drift | `circle_shares` and `circle_notices` have no amount column. The amounts come from the entry. |
| The shop never sees the circle | No shop route reads the circle tables. A member's payment reaches the shop's thread as the usual "Paid ₹X by UPI" card, without the payer's name. Notes go in `circle_notices` on the person's own phone, not in a shop thread. `test_the_shop_never_sees_the_circle` checks this. |
| After leaving, nobody else can pay their bills | `withdraw_all` on leave. `domain.circle.why_not_pay` refuses any bill that is no longer on the list. |
| No interest, fees or shaming words; one palette | Unchanged. `tests/test_schema.py` and `web/tests/rules.test.ts` still pass. |

## Data model (`api/migrations/013_family_circle.sql`)

| Table | One row is |
|---|---|
| `circles` | a circle: its name and who made it |
| `circle_members` | a membership. `left_at` marks a leave; rejoining adds a new row |
| `circle_settings` | the person's own choice (`circle` or `self`). No row means the code default applies. |
| `circle_shares` | an entry on a list. `withdrawn_at` and `withdrawn_why` (`taken_back` or `left`) record its removal. At most one live share per entry. |
| `circle_notices` | an in-app note to one person: `added`, `shared`, `choose`, `kept`, `help` or `paid` |
| `repayments.paid_by` | the member who paid. NULL means the debtor paid, or the payment was cash. |

## API

`GET /people/{p}/circles` · `POST /people/{p}/circle-setting` · `POST /circles` ·
`GET /circles/{c}?person_id=` · `POST /circles/{c}/members` · `POST /circles/{c}/leave` · `POST /circles/{c}/share` ·
`POST /circles/{c}/entries/{e}/take-back` · `POST /circles/{c}/entries/{e}/pay` ·
`POST /circle-notices/{n}/done`

## Left for later, on purpose

- **Consent at joining.** Members are added by the maker (or, later, by any
  member) and go straight in.
  The research's design has each person accept from their own phone and pick
  their setting with nothing pre-selected (DPDP s.6). That would mean a
  `joined_at` set only by the member's own accept, like `customers.linked_at`.
- **The default.** The research recommends not sending bills to the family by
  default. To change it, flip `DEFAULT_ON_UDHAAR` to `"self"`. Nothing in the
  database stores the default.
- **Minors.** No age check. The research suggests no under-18 members at launch,
  with Paytm Pocket Money as the right tool for parents.
- **Limits.** No cooling period after joining and no product cap on circles per
  person. `MOST_MEMBERS = 12` bounds one circle's size, at making and when adding.
- **Removing members and "Not my family".** Only leaving is supported. The maker
  cannot remove anyone yet.
- **Limitation Act s.19.** A family member's part payment could be argued to be
  a payment by the debtor's agent. As before, BAHI never restarts the limitation
  clock on a payment. A lawyer should confirm this before launch.
- **Tonight.** Reminders are unchanged and still go only to the debtor. The
  research suggests holding a reminder for a few days after help was asked.
- **Out of scope for this version:** trust or credit scores, spending limits,
  SMS or WhatsApp, any circle view for the shopkeeper, and Paytm Postpaid.
