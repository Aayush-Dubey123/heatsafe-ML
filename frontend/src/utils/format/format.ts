import type { ExposureLevel } from "../../api/types/types";
import { EXPOSURE_LEVELS } from "../../api/types/types";

/** Format a temperature with one decimal ("32.7"); null becomes an en dash. */
export function fmtTemp(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined || !Number.isFinite(value) ? "–" : value.toFixed(digits);
}

/** Format a distance: metres below 1 km ("450 m"), otherwise kilometres with one decimal ("1.2 km"). */
export function fmtDistance(km: number): string {
  return km < 1 ? `${Math.round(km * 100) * 10} m` : `${km.toFixed(1)} km`;
}

/** Whole-number format with thousands separators for the given locale. */
export function fmtNumber(value: number | null | undefined, locale: string): string {
  return value === null || value === undefined ? "–" : new Intl.NumberFormat(locale).format(value);
}

/** "1 [1–2]" style rank with its 95% interval; the interval is omitted when it is a single rank. */
export function fmtRank(rank: number | null, low: number | null, high: number | null): string {
  if (rank === null) return "–";
  if (low === null || high === null || (low === rank && high === rank)) return String(rank);
  return `${rank} [${low}–${high}]`;
}

export function isExposureLevel(value: unknown): value is ExposureLevel {
  return typeof value === "string" && (EXPOSURE_LEVELS as readonly string[]).includes(value);
}

/** Map an exposure index (0-100) to a bin 0-4 for colouring; matches the API level cut-offs. */
export function exposureBin(index: number): number {
  return [25, 50, 75, 90].filter((cut) => index >= cut).length;
}
