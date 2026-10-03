"use client";

/**
 * Who is holding this phone.
 *
 * In Paytm this is the signed-in account. In the demo there is no sign-in, so the
 * phone remembers a person id and the name he gave on his first scan. Kept in
 * localStorage, read through useSyncExternalStore so the server render and the
 * first client render agree (both say "not known yet"), and every read is in
 * try/catch because a private window can refuse storage: the worst case is that
 * he types his name again.
 */

import { useMemo, useSyncExternalStore } from "react";

export interface Person {
  id: string;
  name: string;
}

const KEY = "bahi.person";
const CHANGED = "bahi:person";

function read(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener("storage", onChange);
  window.addEventListener(CHANGED, onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(CHANGED, onChange);
  };
}

function write(value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, value);
  } catch {
    // Nothing to do: he will be asked his name again next time.
  }
  window.dispatchEvent(new Event(CHANGED));
}

/** undefined while not yet known (server render), null if nobody, else the person. */
export function usePerson(): Person | null | undefined {
  const raw = useSyncExternalStore<string | null | undefined>(subscribe, read, () => undefined);
  return useMemo(() => {
    if (raw === undefined || raw === null) return raw;
    try {
      return JSON.parse(raw) as Person;
    } catch {
      return null;
    }
  }, [raw]);
}

export function newPerson(name: string): Person {
  const p = { id: crypto.randomUUID(), name: name.trim() };
  write(JSON.stringify(p));
  return p;
}

export function usePersonAs(p: Person): void {
  write(JSON.stringify(p));
}

export function forgetPerson(): void {
  write(null);
}
