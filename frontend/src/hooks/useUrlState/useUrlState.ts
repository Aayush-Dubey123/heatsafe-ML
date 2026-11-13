import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { METRIC_LAYERS, SEASONS, TILE_LAYERS } from "../../api/types/types";
import type { MetricLayer, Season, TileLayerId } from "../../api/types/types";

/** Study-area limits used to reject nonsense in a shared link before calling the API. */
const LAT_RANGE: [number, number] = [21.0, 21.3];
const LON_RANGE: [number, number] = [78.9, 79.3];

export interface UrlState {
  lat?: number;
  lon?: number;
  name?: string;
  layer: TileLayerId;
  season: Season;
  metricLayer: MetricLayer;
  zone?: number;
}

function numberInRange(raw: string | null, [min, max]: [number, number]): number | undefined {
  if (raw === null || raw.trim() === "") return undefined;
  const value = Number(raw);
  return Number.isFinite(value) && value >= min && value <= max ? value : undefined;
}

function oneOf<T extends string>(raw: string | null, allowed: readonly T[], fallback: T): T {
  return (allowed as readonly string[]).includes(raw ?? "") ? (raw as T) : fallback;
}

/** Read the shareable app state from URL parameters, ignoring anything invalid. */
export function parseUrlState(params: URLSearchParams): UrlState {
  const lat = numberInRange(params.get("lat"), LAT_RANGE);
  const lon = numberInRange(params.get("lon"), LON_RANGE);
  const hasPoint = lat !== undefined && lon !== undefined;
  const zoneRaw = Number(params.get("zone"));
  return {
    lat: hasPoint ? lat : undefined,
    lon: hasPoint ? lon : undefined,
    name: hasPoint ? (params.get("name")?.slice(0, 60) ?? undefined) : undefined,
    layer: oneOf(params.get("layer"), TILE_LAYERS, "latest_lst"),
    season: oneOf(params.get("season"), SEASONS, "summer"),
    metricLayer: oneOf(params.get("metric"), METRIC_LAYERS, "latest_scene"),
    zone: Number.isInteger(zoneRaw) && zoneRaw > 0 ? zoneRaw : undefined,
  };
}

/** The parts of the URL that should follow the user between pages (their chosen place). */
export function locationSearch(state: UrlState): string {
  if (state.lat === undefined || state.lon === undefined) return "";
  const params = new URLSearchParams({ lat: state.lat.toFixed(5), lon: state.lon.toFixed(5) });
  if (state.name) params.set("name", state.name);
  return `?${params.toString()}`;
}

/**
 * App state kept in the URL so every view is a shareable link.
 * `update` merges changes and removes parameters set to undefined; `replace` avoids history spam.
 */
export function useUrlState() {
  const [params, setParams] = useSearchParams();
  const state = useMemo(() => parseUrlState(params), [params]);

  const update = useCallback(
    (changes: Partial<Record<"lat" | "lon" | "name" | "layer" | "season" | "metric" | "zone", string | number | undefined>>, replace = false) => {
      setParams(
        (previous) => {
          const next = new URLSearchParams(previous);
          for (const [key, value] of Object.entries(changes)) {
            if (value === undefined || value === "") next.delete(key);
            else next.set(key, String(value));
          }
          return next;
        },
        { replace },
      );
    },
    [setParams],
  );

  return { state, update };
}
