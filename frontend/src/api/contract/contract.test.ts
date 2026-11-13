import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";
import { describe, expect, it } from "vitest";

/** The committed API types must be exactly what the frozen OpenAPI snapshot generates (no silent drift). */
describe("API contract", () => {
  it("schema.ts matches the backend OpenAPI snapshot", async () => {
    const snapshot = resolve(__dirname, "../../../../backend/tests/api/openapi_v1.json");
    const ast = await openapiTS(pathToFileURL(snapshot));
    const generated = astToString(ast);
    const committed = readFileSync(resolve(__dirname, "../types/schema.ts"), "utf8");
    const normalise = (text: string) => text.replace(/\s+/g, " ").trim();
    expect(normalise(committed).endsWith(normalise(generated))).toBe(true);
  });
});
