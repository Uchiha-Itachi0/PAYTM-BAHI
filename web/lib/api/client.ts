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
  if (res.status === 204) return undefined as T;
  const data: unknown = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (data as { detail?: unknown }).detail;
    throw new ApiError(res.status, typeof detail === "string" ? detail : res.statusText);
  }
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
        if (!res.ok) throw new ApiError(res.status, res.statusText);
        etag.current = res.headers.get("etag");
        setData((await res.json()) as T);
        setError(undefined);
      } catch (e) {
        if (live) setError(e instanceof Error ? e.message : "offline");
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
