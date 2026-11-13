import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, absoluteTileUrl, apiGet, API_BASE } from "./client";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

afterEach(() => vi.unstubAllGlobals());

describe("apiGet", () => {
  it("builds the URL with params and skips undefined ones", async () => {
    const fetchMock = vi.fn(async (..._args: unknown[]) => json({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await apiGet("/heat", { lat: 21.1, lon: undefined });
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(`${API_BASE}/api/v1/heat?lat=21.1`);
  });

  it("returns parsed JSON on success", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ value: 3 })));
    await expect(apiGet<{ value: number }>("/x")).resolves.toEqual({ value: 3 });
  });

  it("maps the API error envelope to ApiError", async () => {
    const body = { error: { code: "outside_study_area", message: "nope", details: null, request_id: "r1" } };
    vi.stubGlobal("fetch", vi.fn(async () => json(body, 422)));
    const error = await apiGet("/heat").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: "outside_study_area", status: 422, requestId: "r1" });
  });

  it("falls back to http_error when the body is not an envelope", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>", { status: 502 })));
    await expect(apiGet("/x")).rejects.toMatchObject({ code: "http_error", status: 502 });
  });

  it("turns transport failures into network_error without leaking the raw message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch secret-host");
      }),
    );
    const error = (await apiGet("/x").catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe("network_error");
    expect(error.message).not.toContain("secret-host");
  });
});

describe("absoluteTileUrl", () => {
  it("prefixes relative templates and keeps absolute ones", () => {
    expect(absoluteTileUrl("/api/v1/tiles/a/{z}/{x}/{y}.png")).toBe(`${API_BASE}/api/v1/tiles/a/{z}/{x}/{y}.png`);
    expect(absoluteTileUrl("https://cdn.example/t/{z}.png")).toBe("https://cdn.example/t/{z}.png");
  });
});
