import { apiGet } from "../client/client";
import type {
  AreaFeature,
  AssetCategory,
  CoolingSpotsResponse,
  GeoJSONFeatureCollection,
  HeatResponse,
  LocalitySummary,
  MetadataResponse,
  MetricLayer,
  Season,
  ZoneDetail,
  ZoneSummary,
} from "../types/types";

export interface AreaCollection {
  type: "FeatureCollection";
  features: AreaFeature[];
  properties?: Record<string, unknown> | null;
}

export const getMetadata = (signal?: AbortSignal) => apiGet<MetadataResponse>("/metadata", {}, signal);

export const getHeat = (lat: number, lon: number, signal?: AbortSignal) =>
  apiGet<HeatResponse>("/heat", { lat, lon }, signal);

export const getZones = (season: Season, signal?: AbortSignal) =>
  apiGet<ZoneSummary[]>("/zones", { season }, signal);

export const getZone = (zoneId: number, signal?: AbortSignal) =>
  apiGet<ZoneDetail>(`/zones/${zoneId}`, {}, signal);

export const getZonesGeoJson = (season: Season, signal?: AbortSignal) =>
  apiGet<AreaCollection>("/zones/geojson", { season }, signal);

export const getLocalities = (layer: MetricLayer, signal?: AbortSignal) =>
  apiGet<LocalitySummary[]>("/localities", { layer }, signal);

export const getLocalitiesGeoJson = (layer: MetricLayer, signal?: AbortSignal) =>
  apiGet<AreaCollection>("/localities/geojson", { layer }, signal);

export const getCoolingSpots = (
  lat: number,
  lon: number,
  options: { category?: AssetCategory; limit?: number; radiusKm?: number } = {},
  signal?: AbortSignal,
) =>
  apiGet<CoolingSpotsResponse>(
    "/cooling-spots",
    { lat, lon, category: options.category, limit: options.limit ?? 6, radius_km: options.radiusKm ?? 5 },
    signal,
  );

export const getHotspots = (season: Season, signal?: AbortSignal) =>
  apiGet<GeoJSONFeatureCollection>("/hotspots", { season }, signal);
