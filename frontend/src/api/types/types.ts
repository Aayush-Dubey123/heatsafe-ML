import type { components } from "./schema";

/** Friendly aliases for the generated API contract (see `npm run gen:types`). */
type Schemas = components["schemas"];

export type MetadataResponse = Schemas["MetadataResponse"];
export type ProductInfo = Schemas["ProductInfo"];
export type LayerInfo = Schemas["LayerInfo"];
export type HeatResponse = Schemas["HeatResponse"];
export type SeasonExposure = Schemas["SeasonExposure"];
export type ZoneSummary = Schemas["ZoneSummary"];
export type ZoneDetail = Schemas["ZoneDetail"];
export type LocalitySummary = Schemas["LocalitySummary"];
export type CoolingSpot = Schemas["CoolingSpot"];
export type CoolingSpotsResponse = Schemas["CoolingSpotsResponse"];
export type GeoJSONFeatureCollection = Schemas["GeoJSONFeatureCollection"];
export type ErrorResponse = Schemas["ErrorResponse"];

export const SEASONS = ["summer", "monsoon", "post-monsoon", "winter"] as const;
export type Season = (typeof SEASONS)[number];

export const METRIC_LAYERS = ["latest_scene", ...SEASONS] as const;
export type MetricLayer = (typeof METRIC_LAYERS)[number];

export const EXPOSURE_LEVELS = ["low", "moderate", "high", "very_high", "extreme"] as const;
export type ExposureLevel = (typeof EXPOSURE_LEVELS)[number];

export const ASSET_CATEGORIES = [
  "green_space",
  "water_body",
  "health_facility",
  "public_shelter",
  "drinking_water",
] as const;
export type AssetCategory = (typeof ASSET_CATEGORIES)[number];

export const TILE_LAYERS = [
  "latest_lst",
  "lst_summer",
  "lst_monsoon",
  "lst_post-monsoon",
  "lst_winter",
  "exposure_summer",
  "exposure_monsoon",
  "exposure_post-monsoon",
  "exposure_winter",
] as const;
export type TileLayerId = (typeof TILE_LAYERS)[number];

/** GeoJSON feature as returned by the `/zones/geojson` and `/localities/geojson` endpoints. */
export interface AreaFeature {
  type: "Feature";
  geometry: { type: "Polygon" | "MultiPolygon"; coordinates: number[][][] | number[][][][] };
  properties: Record<string, unknown>;
}
