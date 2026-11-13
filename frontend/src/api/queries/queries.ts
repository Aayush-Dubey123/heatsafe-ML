import { useQuery } from "@tanstack/react-query";
import { ApiError } from "../client/client";
import {
  getCoolingSpots,
  getHeat,
  getHotspots,
  getLocalities,
  getLocalitiesGeoJson,
  getMetadata,
  getZones,
  getZonesGeoJson,
} from "../endpoints/endpoints";
import type { AssetCategory, MetadataResponse, MetricLayer, Season } from "../types/types";

const SAVED_METADATA_KEY = "heatsafe.metadata";
const FIVE_MINUTES = 5 * 60_000;
const ONE_HOUR = 60 * 60_000;

/** Retry transient failures (network, 5xx) but never a 4xx: those answers will not change. */
export function shouldRetry(count: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
  return count < 2;
}

function loadSavedMetadata(): MetadataResponse | undefined {
  try {
    const raw = window.localStorage.getItem(SAVED_METADATA_KEY);
    return raw ? (JSON.parse(raw) as MetadataResponse) : undefined;
  } catch {
    return undefined;
  }
}

function saveMetadata(data: MetadataResponse): MetadataResponse {
  try {
    window.localStorage.setItem(SAVED_METADATA_KEY, JSON.stringify(data));
  } catch {
    /* storage may be full or blocked: saving is a convenience only */
  }
  return data;
}

/** Product description. The last good copy is kept so the app can open offline. */
export function useMetadata() {
  return useQuery({
    queryKey: ["metadata"],
    queryFn: async ({ signal }) => saveMetadata(await getMetadata(signal)),
    staleTime: FIVE_MINUTES,
    retry: shouldRetry,
    initialData: loadSavedMetadata,
    initialDataUpdatedAt: 0,
  });
}

/** Heat answer for a point; coordinates are rounded so nearby taps share a cache entry. */
export function useHeat(lat?: number, lon?: number) {
  const key = lat === undefined || lon === undefined ? undefined : ([lat.toFixed(5), lon.toFixed(5)] as const);
  return useQuery({
    queryKey: ["heat", key],
    queryFn: ({ signal }) => getHeat(Number(key?.[0]), Number(key?.[1]), signal),
    enabled: key !== undefined,
    staleTime: FIVE_MINUTES,
    retry: shouldRetry,
  });
}

export function useCoolingSpots(lat?: number, lon?: number, category?: AssetCategory) {
  const enabled = lat !== undefined && lon !== undefined;
  return useQuery({
    queryKey: ["cooling", lat?.toFixed(4), lon?.toFixed(4), category],
    queryFn: ({ signal }) => getCoolingSpots(lat as number, lon as number, { category }, signal),
    enabled,
    staleTime: ONE_HOUR,
    retry: shouldRetry,
  });
}

export function useZones(season: Season) {
  return useQuery({
    queryKey: ["zones", season],
    queryFn: ({ signal }) => getZones(season, signal),
    staleTime: FIVE_MINUTES,
    retry: shouldRetry,
  });
}

export function useZonesGeoJson(season: Season) {
  return useQuery({
    queryKey: ["zones-geojson", season],
    queryFn: ({ signal }) => getZonesGeoJson(season, signal),
    staleTime: FIVE_MINUTES,
    retry: shouldRetry,
  });
}

export function useLocalities(layer: MetricLayer) {
  return useQuery({
    queryKey: ["localities", layer],
    queryFn: ({ signal }) => getLocalities(layer, signal),
    staleTime: FIVE_MINUTES,
    retry: shouldRetry,
  });
}

/** Locality polygons: used for search (names + centres) and for map outlines. */
export function useLocalitiesGeoJson(layer: MetricLayer = "latest_scene") {
  return useQuery({
    queryKey: ["localities-geojson", layer],
    queryFn: ({ signal }) => getLocalitiesGeoJson(layer, signal),
    staleTime: ONE_HOUR,
    retry: shouldRetry,
  });
}

export function useHotspots(season: Season, enabled = true) {
  return useQuery({
    queryKey: ["hotspots", season],
    queryFn: ({ signal }) => getHotspots(season, signal),
    enabled,
    staleTime: ONE_HOUR,
    retry: shouldRetry,
  });
}
