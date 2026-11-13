import type { AreaCollection } from "../../api/endpoints/endpoints";
import type {
  AssetCategory,
  CoolingSpotsResponse,
  HeatResponse,
  LocalitySummary,
  MetadataResponse,
  ZoneSummary,
} from "../../api/types/types";
import { SEASONS } from "../../api/types/types";

/** Realistic API answers (shaped like the frozen OpenAPI contract) used by tests. */
export const product = {
  version: "2026-11-03_LC09_test",
  scene_id: "LC09_L2SP_144045_20261103_02_T1",
  scene_date: "2026-11-03",
  scene_age_days: 10,
  stale: false,
  model_version: "m1-20261109T150313Z",
  published_utc: "2026-11-11T06:02:53+00:00",
  observed_fraction: 0.83,
};

const tileLayer = (id: string, kind: "lst" | "exposure", season: string | null) => ({
  id,
  kind,
  season,
  tile_url: `/api/v1/tiles/${id}/{z}/{x}/{y}.png`,
  vmin: kind === "lst" ? 20 : 0,
  vmax: kind === "lst" ? 60 : 100,
  unit: kind === "lst" ? "deg C" : "index 0-100",
});

export const metadata: MetadataResponse = {
  product,
  bounds: [78.937, 21.041, 79.212, 21.259],
  center: [79.07, 21.15],
  zoom_min: 10,
  zoom_max: 16,
  layers: [
    tileLayer("latest_lst", "lst", null),
    ...SEASONS.map((s) => tileLayer(`lst_${s}`, "lst", s)),
    ...SEASONS.map((s) => tileLayer(`exposure_${s}`, "exposure", s)),
  ],
  seasons: [...SEASONS],
  exposure_levels: ["low", "moderate", "high", "very_high", "extreme"],
  variable: "land_surface_temperature",
  resolution_note: "30 m analytical grid. Landsat thermal is natively ~100 m resampled to 30 m.",
  disclaimers: ["Research tool, not an official warning system."],
};

export const heat: HeatResponse = {
  latitude: 21.1458,
  longitude: 79.0882,
  covered: true,
  lst_celsius: 32.71,
  lst_p05: 31.04,
  lst_p95: 34.52,
  observed: true,
  locality: { id: 35, name: "Nagpur and Sitabuldi" },
  zone: { id: 4, name: "Dhantoli" },
  seasons: {
    summer: { mean_lst_celsius: 44.5, exposure_index: 57.6, exposure_level: "high" },
    monsoon: { mean_lst_celsius: 46.7, exposure_index: 51.2, exposure_level: "high" },
    "post-monsoon": { mean_lst_celsius: 34.9, exposure_index: 44.0, exposure_level: "moderate" },
    winter: { mean_lst_celsius: 30.2, exposure_index: 40.3, exposure_level: "moderate" },
  },
  product,
  note: "Surface temperature estimate with a 90% range.",
};

export const cooling: CoolingSpotsResponse = {
  latitude: 21.1458,
  longitude: 79.0882,
  radius_km: 5,
  count: 3,
  source: "OpenStreetMap contributors (ODbL); completeness varies",
  spots: [
    { asset_id: "osm-node-1", category: "drinking_water", name: null, latitude: 21.147, longitude: 79.09, distance_km: 0.441 },
    { asset_id: "osm-node-2", category: "health_facility", name: "Dik Hospital", latitude: 21.148, longitude: 79.091, distance_km: 0.503 },
    { asset_id: "osm-node-3", category: "green_space", name: "Futala Garden", latitude: 21.149, longitude: 79.07, distance_km: 2.1 },
  ] as { asset_id: string; category: AssetCategory; name: string | null; latitude: number; longitude: number; distance_km: number }[],
};

export const zone = (id: number, name: string, overrides: Partial<ZoneSummary> = {}): ZoneSummary => ({
  zone_id: id,
  zone_name: name,
  area_km2: 8.8,
  season: "summer",
  mean_lst_celsius: 43.6,
  exposure_index: 37.5,
  exposure_index_ci_low: 33.4,
  exposure_index_ci_high: 41.7,
  exposure_level: "moderate",
  exposure_rank: id,
  vulnerability_score: 82.6,
  risk_score: 60.0,
  risk_rank: id,
  risk_rank_low: 1,
  risk_rank_high: 2,
  population: 182408,
  population_density_per_km2: 20777.8,
  share_age_60_plus: 0.1096,
  green_deficit: 0.77,
  assets: { green_space: 21, health_facility: 56, public_shelter: 0 },
  ...overrides,
});

export const zones: ZoneSummary[] = [
  zone(1, "Gandhibagh", { risk_score: 60.0, risk_rank: 1, risk_rank_low: 1, risk_rank_high: 2 }),
  zone(2, "Satranjipura", { risk_score: 57.9, risk_rank: 2, risk_rank_low: 1, risk_rank_high: 4, exposure_index: 36.3 }),
  zone(3, "Mangalwari", { risk_score: 37.2, risk_rank: 3, risk_rank_low: 3, risk_rank_high: 3, exposure_index: 45.2, vulnerability_score: 36.8 }),
];

const square = (west: number, south: number, size: number) => ({
  type: "Polygon" as const,
  coordinates: [[[west, south], [west + size, south], [west + size, south + size], [west, south + size], [west, south]]],
});

export const zonesGeo: AreaCollection = {
  type: "FeatureCollection",
  properties: { season: "summer", boundary_quality: "approximate; not an official zone map" },
  features: zones.map((z, i) => ({
    type: "Feature" as const,
    geometry: square(79.0 + i * 0.05, 21.1, 0.045),
    properties: { ...z },
  })),
};

export const localitiesGeo: AreaCollection = {
  type: "FeatureCollection",
  properties: { layer: "latest_scene" },
  features: [
    { type: "Feature", geometry: square(79.07, 21.13, 0.02), properties: { locality_id: 1, locality_name: "Dhantoli" } },
    { type: "Feature", geometry: square(79.04, 21.12, 0.02), properties: { locality_id: 2, locality_name: "Ajni" } },
    { type: "Feature", geometry: square(79.09, 21.16, 0.02), properties: { locality_id: 3, locality_name: "Gadaga" } },
  ],
};

export const localities: LocalitySummary[] = [
  { locality_id: 1, locality_name: "Dhantoli", area_km2: 1.5, in_extended_limit: false, layer: "summer", mean_lst_celsius: 43.1, exposure_index: 28.9, exposure_level: "moderate" },
  { locality_id: 2, locality_name: "Ajni", area_km2: 4.6, in_extended_limit: false, layer: "summer", mean_lst_celsius: 46.0, exposure_index: 63.0, exposure_level: "high" },
  { locality_id: 3, locality_name: "Hudkeshwar", area_km2: 4.3, in_extended_limit: true, layer: "summer", mean_lst_celsius: 45.0, exposure_index: 52.0, exposure_level: "high" },
];

export const emptyCollection = { type: "FeatureCollection", features: [] };
