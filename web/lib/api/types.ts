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
