"""The family circle on the wire. Only a member's own phone ever gets these."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from bahi.domain.circle import MOST_MEMBERS
from bahi.service.models import ShopOut

OnUdhaar = Literal["circle", "self"]
NoticeKind = Literal["added", "shared", "choose", "kept", "help", "paid"]


class CircleIn(BaseModel):
    """A new circle: its name, and the people in it by mobile number."""

    person_id: UUID
    name: str = Field(min_length=1, max_length=40)
    phones: list[str] = Field(min_length=1, max_length=MOST_MEMBERS - 1)


class MemberIn(BaseModel):
    """One more person for a circle, by mobile number."""

    person_id: UUID
    phone: str = Field(min_length=1, max_length=15)


class OnUdhaarIn(BaseModel):
    """What should happen to their next udhaar."""

    on_udhaar: OnUdhaar


class ShareIn(BaseModel):
    """ "Add to circle": one of their own open entries, onto this circle's list."""

    person_id: UUID
    entry_id: UUID


class CirclePayIn(BaseModel):
    """A member pays an entry on the list by UPI."""

    person_id: UUID
    #: None pays everything left on the entry.
    amount_paise: int | None = Field(default=None, gt=0)


class MemberOut(BaseModel):
    person_id: str
    #: The name on their Paytm account.
    name: str
    me: bool
    #: They made the circle.
    made_it: bool


class CirclePaymentOut(BaseModel):
    payer_name: str
    #: The debtor paid it themselves (in the circle, or in their own book).
    by_debtor: bool
    amount_paise: int
    paid_at: datetime


class CircleEntryOut(BaseModel):
    """An entry on the list: the shop, the amount, the date. Never the item."""

    entry_id: str
    debtor_name: str
    debtor_person_id: str
    #: It is the viewer's own.
    mine: bool
    shop: ShopOut
    amount_paise: int
    paid_paise: int
    left_paise: int
    recorded_at: datetime
    shared_at: datetime
    #: open: anyone here can pay it. paid: nothing left. closed: the shop took it
    #: back or corrected it, or it is past the limitation line; nothing to pay.
    state: Literal["open", "paid", "closed"]
    payments: list[CirclePaymentOut]


class CircleOut(BaseModel):
    id: str
    name: str
    created_at: datetime
    members: list[MemberOut]
    #: The list, newest first.
    entries: list[CircleEntryOut]
    #: What is left to pay on the list.
    open_paise: int


class CircleSummaryOut(BaseModel):
    id: str
    name: str
    #: Everyone in it, by the name on their Paytm account.
    members: list[str]
    open_paise: int
    open_count: int


class NoticeOut(BaseModel):
    id: str
    kind: NoticeKind
    body: str
    circle_id: str | None
    entry_id: str | None
    #: The shop the entry is at, for "Pay it myself".
    shop_id: str | None
    created_at: datetime


class ListedOut(BaseModel):
    """One of the viewer's own entries, on a circle's list."""

    entry_id: str
    circle_id: str
    circle_name: str


class MyCirclesOut(BaseModel):
    person_id: str
    #: What happens to their next udhaar.
    on_udhaar: OnUdhaar
    #: They chose it; False means the default is deciding.
    chosen: bool
    default_on_udhaar: OnUdhaar
    circles: list[CircleSummaryOut]
    #: Notes waiting for them, newest first.
    notices: list[NoticeOut]
    #: Their own entries on a list now.
    listed: list[ListedOut]


class CirclePaidOut(BaseModel):
    circle_id: str
    entry_id: str
    shop: ShopOut
    debtor_name: str
    amount_paise: int
    #: What is still left on this entry after it.
    left_paise: int
    paid_at: datetime
