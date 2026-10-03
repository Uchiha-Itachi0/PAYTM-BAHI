/**
 * The frontend's rules, checked against the source.
 *
 * 1. No figure is typed into a screen. Every amount comes from the API; a "₹200"
 *    written into a component goes stale the first time the seed moves.
 * 2. No shaming words anywhere in the UI.
 * 3. The palette lives in one file. A colour written inline is a colour the
 *    token file does not know about.
 *
 * Comments are stripped first, so a comment may quote a rule ("never 'I'll pay
 * by Friday'") without tripping it.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const WEB = path.resolve(__dirname, "..");
const SOURCE_DIRS = ["app", "components"];

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) return files(full);
    return /\.tsx?$/.test(name) ? [full] : [];
  });
}

function code(file: string): string {
  return readFileSync(file, "utf-8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "")
    .replace(/\{\s*\/\*[\s\S]*?\*\/\s*\}/g, "");
}

const sources = SOURCE_DIRS.flatMap((d) => files(path.join(WEB, d)));
const rel = (f: string): string => path.relative(WEB, f);

describe("the UI source", () => {
  it("has files to check", () => {
    expect(sources.length).toBeGreaterThan(5);
  });

  it("types no amount into any screen", () => {
    const typed = sources.filter((f) => /₹\s*\d/.test(code(f))).map(rel);
    expect(typed).toEqual([]);
  });

  it("never calls anyone overdue or a defaulter", () => {
    const words = /\b(overdue|defaulter|blacklist|late fee)\b/i;
    const found = sources.filter((f) => words.test(code(f))).map(rel);
    expect(found).toEqual([]);
  });

  it("defines no colour outside globals.css", () => {
    const hex = /#[0-9a-fA-F]{3,8}\b/;
    const inline = sources.filter((f) => hex.test(code(f))).map(rel);
    expect(inline).toEqual([]);
  });
});
