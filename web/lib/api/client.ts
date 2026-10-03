"use client";

/**
 * Talking to the API from the browser.
 *
 * Every call goes to /api on the same origin, and Next forwards it to FastAPI
 * (next.config.ts). So a judge's phone needs one URL, and there is no CORS to get
 * wrong on the day.
 *
 * `usePoll` is how both screens stay live: ask every two seconds, send back the
 * ETag we have, and get an empty 304 when nothing changed. No websockets:
 * bulletproof beats elegant with a phone on venue 4G.
 */

import { useCallback, useEffect, useRef, useState } from "react";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  return read<T>(res);
}

/** A DELETE: forgetting something. */
export async function apiDelete(path: string): Promise<void> {
  const res = await fetch(`/api${path}`, { method: "DELETE", cache: "no-store" });
  return read<void>(res);
}

/** A POST of a file (a recording), as multipart form data. */
export async function apiForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`/api${path}`, { method: "POST", body: form, cache: "no-store" });
  return read<T>(res);
}

/** What the API's checks are called on screen. */
const FIELDS: Record<string, string> = {
  tag: "Where they live or work",
  new_tag: "Where they live or work",
  display_name: "Name",
  new_name: "Name",
  query: "Mobile number or UPI ID",
};

/**
 * Words for a refusal. The API says why in `detail`: a sentence, or (when a
 * field failed its check) a list, which becomes "Name: String should have at
 * most 40 characters". Never just the status's name: over HTTP/2 there is none,
 * and "Unprocessable Content" tells nobody what to fix.
 */
export function refusal(status: number, detail: unknown): string {
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { loc?: unknown[]; msg?: string };
    const field = String(first.loc?.at(-1) ?? "");
    const what = FIELDS[field] ?? field;
    return [what, first.msg].filter(Boolean).join(": ");
  }
  if (status === 502 || status === 503 || status === 504)
    return "The server isn't answering right now. Try again in a minute.";
  return `Something went wrong (${status}).`;
}

async function read<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as T;
  const data: unknown = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, refusal(res.status, (data as { detail?: unknown }).detail));
  return data as T;
}

export function usePoll<T>(
  path: string | null,
  every = 2000,
): { data: T | undefined; error: string | undefined; refresh: () => void } {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<string>();
  const etag = useRef<string | null>(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    etag.current = null;
  }, [path]);

  useEffect(() => {
    if (!path) return;
    let live = true;

    async function load(): Promise<void> {
      try {
        const res = await fetch(`/api${path}`, {
          headers: etag.current ? { "If-None-Match": etag.current } : undefined,
          cache: "no-store",
        });
        if (!live || res.status === 304) return;
        if (!res.ok) {
          const data: unknown = await res.json().catch(() => ({}));
          throw new ApiError(res.status, refusal(res.status, (data as { detail?: unknown }).detail));
        }
        etag.current = res.headers.get("etag");
        setData((await res.json()) as T);
        setError(undefined);
      } catch (e) {
        if (live) setError((e instanceof Error && e.message) || "offline");
      }
    }

    void load();
    const timer = setInterval(() => void load(), every);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [path, every, tick]);

  return { data, error, refresh };
}
