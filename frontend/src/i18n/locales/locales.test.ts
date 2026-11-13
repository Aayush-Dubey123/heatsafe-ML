import { describe, expect, it } from "vitest";
import en from "./en.json";
import hi from "./hi.json";
import mr from "./mr.json";

function keys(node: unknown, prefix = ""): string[] {
  if (Array.isArray(node)) return [`${prefix}[${node.length}]`];
  if (node && typeof node === "object") {
    return Object.entries(node).flatMap(([k, v]) => keys(v, prefix ? `${prefix}.${k}` : k));
  }
  return [prefix];
}

function placeholders(node: unknown): string[] {
  return JSON.stringify(node).match(/\{\{\w+\}\}/g)?.sort() ?? [];
}

describe("translations", () => {
  it.each([["hi", hi], ["mr", mr]])("%s has exactly the English keys and list lengths", (_name, locale) => {
    expect(keys(locale).sort()).toEqual(keys(en).sort());
  });

  it.each([["hi", hi], ["mr", mr]])("%s keeps every interpolation placeholder", (_name, locale) => {
    expect(placeholders(locale)).toEqual(placeholders(en));
  });
});
