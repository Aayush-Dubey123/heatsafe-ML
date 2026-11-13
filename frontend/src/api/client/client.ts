import type { ErrorResponse } from "../types/types";

const DEFAULT_BASE = "http://127.0.0.1:8000";
const TIMEOUT_MS = 15_000;

/** Base URL of the HeatSafe API (public config; set VITE_API_BASE_URL). */
export const API_BASE: string = (
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? DEFAULT_BASE
).replace(/\/+$/, "");

/**
 * A failed API call in a stable shape the UI can branch on.
 * `code` comes from the API error envelope (e.g. `outside_study_area`); transport failures use `network_error`.
 */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly requestId?: string;

  constructor(code: string, message: string, status: number, requestId?: string) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.requestId = requestId;
  }
}

type Params = Record<string, string | number | undefined>;

function withTimeout(signal?: AbortSignal): AbortSignal {
  const timeout = AbortSignal.timeout(TIMEOUT_MS);
  return signal && "any" in AbortSignal ? AbortSignal.any([signal, timeout]) : (signal ?? timeout);
}

/**
 * GET a JSON resource from `/api/v1`.
 * Normalises every failure into an {@link ApiError}; raw exception text is never shown to users.
 */
export async function apiGet<T>(path: string, params: Params = {}, signal?: AbortSignal): Promise<T> {
  const url = new URL(`${API_BASE}/api/v1${path}`);
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) url.searchParams.set(key, String(value));
  }

  let response: Response;
  try {
    response = await fetch(url, { headers: { Accept: "application/json" }, signal: withTimeout(signal) });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError("network_error", "The service could not be reached.", 0);
  }

  if (!response.ok) {
    let envelope: Partial<ErrorResponse> | undefined;
    try {
      envelope = (await response.json()) as Partial<ErrorResponse>;
    } catch {
      envelope = undefined;
    }
    const body = envelope?.error;
    throw new ApiError(
      body?.code ?? "http_error",
      body?.message ?? response.statusText,
      response.status,
      body?.request_id,
    );
  }
  return (await response.json()) as T;
}

/** Absolute URL for a tile URL template returned by `/metadata` (which is relative to the API). */
export function absoluteTileUrl(template: string): string {
  return template.startsWith("http") ? template : `${API_BASE}${template}`;
}
