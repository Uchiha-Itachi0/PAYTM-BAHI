"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { CustomerShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Notice } from "@/components/ui/Notice";
import { Pill } from "@/components/ui/Pill";
import { api, ApiError } from "@/lib/api/client";
import type { CircleView } from "@/lib/api/types";
import { usePerson } from "@/lib/person";

/**
 * C2 · Make a circle: a name, and the family by their mobile numbers. Each
 * number finds a Paytm account and is not kept. He is in it too. Everyone added
 * is told on their own phone.
 */

const MOST = 11;

export function NewCircleScreen(): React.ReactElement {
  const person = usePerson();
  const router = useRouter();
  const [name, setName] = useState("");
  const [phones, setPhones] = useState<string[]>([""]);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const filled = phones.map((p) => p.trim()).filter(Boolean);
  const ready = name.trim().length > 0 && filled.length > 0 && !busy;

  async function make(): Promise<void> {
    if (!person) return;
    setBusy(true);
    setProblem(null);
    try {
      const made = await api<CircleView>("/circles", {
        person_id: person.id,
        name: name.trim(),
        phones: filled,
      });
      router.push(`/c/circle/${made.id}`);
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : "That didn't go through.");
      setBusy(false);
    }
  }

  const heading = { title: "Make a circle", back: "/c/circle" };
  if (person === null) {
    return (
      <CustomerShell heading={heading}>
        <Notice>Pick whose phone this is on the home screen first.</Notice>
      </CustomerShell>
    );
  }

  return (
    <CustomerShell heading={heading}>
      {problem ? <Notice tone="warn">{problem}</Notice> : null}
      <Card>
        <Field
          label="Name"
          value={name}
          onChange={setName}
          placeholder="Sharma family"
          maxLength={40}
          autoFocus
        />
      </Card>
      <Card title="Who is in it" tight>
        <div className="flex flex-col gap-2.5">
          {phones.map((p, i) => (
            <Field
              key={i}
              label={`Mobile number ${i + 1}`}
              value={p}
              onChange={(v) => setPhones(phones.map((old, j) => (j === i ? v : old)))}
              placeholder="10-digit mobile number"
              inputMode="tel"
              maxLength={15}
            />
          ))}
        </div>
        {phones.length < MOST ? (
          <button
            type="button"
            onClick={() => setPhones([...phones, ""])}
            className="mt-3 text-[13px] font-extrabold text-cyan-text"
          >
            + Add another person
          </button>
        ) : null}
        <p className="mt-2 text-[11.5px] font-medium leading-normal text-sub">
          You are in it too. Each number must be on Paytm; the number only finds the
          account and is not kept.
        </p>
      </Card>
      <Pill onClick={() => void make()} disabled={!ready}>
        Make the circle
      </Pill>
    </CustomerShell>
  );
}
