import type { AreaFeature } from "../../api/types/types";

type Ring = number[][];

/** Planar area of a ring (shoelace formula, coordinates in degrees: fine for ranking pieces of one city). */
export function ringArea(ring: Ring): number {
  let sum = 0;
  for (let i = 0; i < ring.length - 1; i++) {
    const [x1 = 0, y1 = 0] = ring[i] ?? [];
    const [x2 = 0, y2 = 0] = ring[i + 1] ?? [];
    sum += x1 * y2 - x2 * y1;
  }
  return sum / 2;
}

/** Centroid of a ring as [lon, lat]; falls back to the vertex average for degenerate rings. */
export function ringCentroid(ring: Ring): [number, number] {
  const area = ringArea(ring);
  if (Math.abs(area) < 1e-12) {
    const n = Math.max(ring.length, 1);
    return [ring.reduce((s, p) => s + (p[0] ?? 0), 0) / n, ring.reduce((s, p) => s + (p[1] ?? 0), 0) / n];
  }
  let cx = 0;
  let cy = 0;
  for (let i = 0; i < ring.length - 1; i++) {
    const [x1 = 0, y1 = 0] = ring[i] ?? [];
    const [x2 = 0, y2 = 0] = ring[i + 1] ?? [];
    const cross = x1 * y2 - x2 * y1;
    cx += (x1 + x2) * cross;
    cy += (y1 + y2) * cross;
  }
  return [cx / (6 * area), cy / (6 * area)];
}

/** Outer rings of a polygon or multi-polygon feature. */
export function outerRings(feature: AreaFeature): Ring[] {
  const { type, coordinates } = feature.geometry;
  if (type === "Polygon") return [(coordinates as number[][][])[0] ?? []];
  return (coordinates as number[][][][]).map((polygon) => polygon[0] ?? []);
}

/** Centre of the largest piece of a feature, as {lat, lon}. */
export function featureCenter(feature: AreaFeature): { lat: number; lon: number } {
  const rings = outerRings(feature).filter((r) => r.length > 2);
  const largest = rings.reduce<Ring>((best, ring) => (Math.abs(ringArea(ring)) > Math.abs(ringArea(best)) ? ring : best), rings[0] ?? []);
  const [lon, lat] = ringCentroid(largest);
  return { lat, lon };
}

/** Bounding box [west, south, east, north] of many features. */
export function boundsOf(features: AreaFeature[]): [number, number, number, number] {
  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;
  for (const feature of features) {
    for (const ring of outerRings(feature)) {
      for (const [lon = 0, lat = 0] of ring) {
        west = Math.min(west, lon);
        east = Math.max(east, lon);
        south = Math.min(south, lat);
        north = Math.max(north, lat);
      }
    }
  }
  return [west, south, east, north];
}

/**
 * Equirectangular projection (scaled by cos of the middle latitude) fitted into a `width` x `height` box
 * for the given bounds. Returns a function from [lon, lat] to SVG [x, y].
 */
export function makeProjector(
  bounds: [number, number, number, number],
  width: number,
  height: number,
  padding = 6,
): (lon: number, lat: number) => [number, number] {
  const [west, south, east, north] = bounds;
  const cosLat = Math.cos((((south + north) / 2) * Math.PI) / 180);
  const spanX = (east - west) * cosLat;
  const spanY = north - south;
  const scale = Math.min((width - 2 * padding) / spanX, (height - 2 * padding) / spanY);
  const offsetX = (width - spanX * scale) / 2;
  const offsetY = (height - spanY * scale) / 2;
  return (lon, lat) => [offsetX + (lon - west) * cosLat * scale, offsetY + (north - lat) * scale];
}

/** SVG path data for a feature using a projector from {@link makeProjector}. */
export function svgPath(feature: AreaFeature, project: (lon: number, lat: number) => [number, number]): string {
  return outerRings(feature)
    .map((ring) => `M${ring.map(([lon = 0, lat = 0]) => project(lon, lat).map((n) => n.toFixed(1)).join(",")).join("L")}Z`)
    .join("");
}

/** Link that opens a place on OpenStreetMap (no account, no tracking). */
export function osmPlaceLink(lat: number, lon: number): string {
  return `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=18/${lat}/${lon}`;
}

/** Link that opens turn-by-turn directions to a place in Google Maps (opened only when the user taps it). */
export function directionsLink(lat: number, lon: number): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}`;
}
