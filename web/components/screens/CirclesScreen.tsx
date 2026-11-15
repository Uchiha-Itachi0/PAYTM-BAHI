"use client";

import Link from "next/link";

import { CircleNotices } from "@/components/customer/CircleNotices";
import { CustomerShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Dots, Notice } from "@/components/ui/Notice";
import { Pill } from "@/components/ui/Pill";
import { Avatar } from "@/components/ui/Row";
import { api, usePoll } from "@/lib/api/client";
import type { MyCircles } from "@/lib/api/types";
import { formatPaise } from "@/lib/money";
import { usePerson } from "@/lib/person";

/**
 * C1 · Family circle: the people who can pay each other's udhaar, at any shop.
 *
 * His notes first, then what happens to his next udhaar (his setting, with the
 * default named when he hasn't chosen), then each circle he is in. Paying for
 * someone is always a choice, and nobody in a circle ever owes anyone else's.
 */

const SETTINGS = [
  { value: "circle", label: "Send to my circle", sub: "Anyone in it can pay it" },
  { value: "self", label: "Keep it to myself", sub: "I pay it; I can still add it" },
] as const;

export function CirclesScreen(): React.ReactElement {
  const person = usePerson();
  const mine = usePoll<MyCircles>(person ? `/people/${person.id}/circles` : null);
  const heading = { title: "Family circle", back: "/c" };
  const m = mine.data;

  async function choose(value: "circle" | "self"): Promise<void> {
    if (!person) return;
    await api(`/people/${person.id}/circle-setting`, { on_udhaar: value });
    mine.refresh();
  }

  if (person === null) {
    return (
      <CustomerShell heading={heading}>
        <Notice>Pick whose phone this is on the home screen first.</Notice>
      </CustomerShell>
    );
  }

  return (
    <CustomerShell heading={heading}>
      {!m || !person ? (
        <Card>
          <Dots />
        </Card>
      ) : (
        <>
          <CircleNotices mine={m} personId={person.id} refresh={mine.refresh} />

          <Card title="When I take udhaar" tight>
            <div className="grid grid-cols-2 gap-2">
              {SETTINGS.map((s) => (
                <button
                  key={s.value}
                  type="button"
                  aria-pressed={m.on_udhaar === s.value}
                  onClick={() => void choose(s.value)}
                  className={`rounded-[12px] border-[1.5px] px-3 py-2.5 text-left ${m.on_udhaar === s.value ? "border-cyan bg-tile" : "border-line"}`}
                >
                  <p className="text-[13.5px] font-extrabold">{s.label}</p>
                  <p className="mt-0.5 text-[11.5px] font-medium leading-snug text-sub">{s.sub}</p>
                </button>
              ))}
            </div>
            <p className="mt-2 text-[11.5px] font-medium text-sub">
              {m.chosen
                ? "Your choice. Change it any time."
                : "You haven't chosen, so this is the default. Change it any time."}{" "}
              In more than one circle, you pick which one each time.
            </p>
          </Card>

          {m.circles.length ? (
            <Card title="My circles" tight>
              {m.circles.map((c) => (
                <Link
                  key={c.id}
                  href={`/c/circle/${c.id}`}
                  className="flex items-center gap-3 border-b border-hair py-3 last:border-b-0"
                >
                  <Avatar name={c.name} />
                  <div className="min-w-0 flex-1">
                    <p className="text-[14.5px] font-extrabold">{c.name}</p>
                    <p className="mt-0.5 truncate text-[12px] font-medium text-sub">
                      {c.members.join(", ")}
                    </p>
                  </div>
                  <p className="flex-none text-right text-[12px] font-semibold text-sub">
                    {c.open_count ? (
                      <>
                        <b className="block text-[14.5px] font-extrabold tabular-nums text-ink">
                          {formatPaise(c.open_paise)}
                        </b>
                        {c.open_count} open
                      </>
                    ) : (
                      "Nothing open"
                    )}
                  </p>
                </Link>
              ))}
            </Card>
          ) : (
            <Notice>
              You&apos;re not in a circle yet. Make one with your family: anyone in it can pay
              udhaar on its list, at any shop.
            </Notice>
          )}

          <Pill href="/c/circle/new">Make a circle</Pill>
          <p className="text-center text-[11.5px] font-medium leading-normal text-sub">
            Paying for someone is always a choice. Nobody in a circle owes anyone
            else&apos;s udhaar, and shops never see your circle.
          </p>
        </>
      )}
    </CustomerShell>
  );
}
