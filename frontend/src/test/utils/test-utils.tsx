import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { vi } from "vitest";
import {
  cooling,
  emptyCollection,
  heat,
  localities,
  localitiesGeo,
  metadata,
  zones,
  zonesGeo,
} from "../fixtures/fixtures";

type Reply = unknown | { __status: number; body: unknown } | (() => Response);

const DEFAULTS: Record<string, Reply> = {
  "/metadata": metadata,
  "/heat": heat,
  "/cooling-spots": cooling,
  "/zones": zones,
  "/zones/geojson": zonesGeo,
  "/localities": localities,
  "/localities/geojson": localitiesGeo,
  "/hotspots": emptyCollection,
};

export function apiError(status: number, code: string, message: string) {
  return { __status: status, body: { error: { code, message, details: null, request_id: "req-test" } } };
}

/** Stub `fetch` with in-memory API answers; returns the list of requested paths for assertions. */
export function mockApi(overrides: Record<string, Reply> = {}) {
  const calls: string[] = [];
  const handler = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input));
    const path = url.pathname.replace("/api/v1", "");
    calls.push(`${path}${url.search}`);
    const reply = path in overrides ? overrides[path] : DEFAULTS[path];
    if (typeof reply === "function") return (reply as () => Response)();
    if (reply === undefined) {
      return new Response(JSON.stringify(apiError(404, "not_found", "missing").body), { status: 404 });
    }
    if (typeof reply === "object" && reply !== null && "__status" in reply) {
      const { __status, body } = reply as { __status: number; body: unknown };
      return new Response(JSON.stringify(body), { status: __status });
    }
    return new Response(JSON.stringify(reply), { status: 200, headers: { "content-type": "application/json" } });
  });
  vi.stubGlobal("fetch", handler);
  return { calls, handler };
}

/** Shows the current URL so tests can assert on shareable state. */
export function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname + location.search}</output>;
}

/** Render with the same providers as the real app (query cache, router, i18n comes from the test setup). */
export function renderWithProviders(ui: ReactElement, route = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        {ui}
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
