/**
 * The API's shapes, named. Generated from contract/openapi.json (`npm run types`),
 * which FastAPI builds from the Pydantic models. A field renamed on the server
 * breaks the type check here, not a screen in front of a judge.
 */

import type { components } from "./schema";

type S = components["schemas"];

export type ShopBook = S["ShopBookOut"];
export type Book = S["BookOut"];
export type BookLine = S["LineOut"];
export type Shop = S["ShopOut"];
export type Counter = S["CounterOut"];
export type Waiting = S["WaitingOut"];
export type Entry = S["EntryOut"];
export type ScanState = S["ScanOut"];
export type Joined = S["JoinOut"];
export type Customer = S["CustomerOut"];
export type Heard = S["HeardOut"];
export type Answer = S["AnswerOut"];
export type HeardPerson = S["PersonOut"];
export type Clip = S["ClipOut"];
export type Munshi = S["MunshiOut"];
export type MunshiCard = S["CardOut"];
export type Thread = S["ThreadOut"];
export type ThreadEntry = S["ThreadEntryOut"];
export type Message = S["MessageOut"];
export type Inbox = S["InboxOut"];
export type InboxRow = S["InboxRowOut"];
export type Replies = S["RepliesOut"];
export type MyUdhaar = S["MyUdhaarOut"];
export type MyShop = S["MyShopOut"];
export type Invite = S["InviteOut"];
export type Paid = S["PaidOut"];
export type DemoPhone = S["DemoPhoneOut"];
export type Account = S["AccountOut"];
export type Tonight = S["TonightOut"];
export type Plan = S["PlanOut"];
export type Reminder = S["ReminderOut"];
export type Events = S["EventsOut"];
export type ShopEvent = S["EventOut"];
export type CustomerDetail = S["CustomerDetailOut"];
