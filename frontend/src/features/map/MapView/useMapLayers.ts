import { useEffect } from "react";
import type { GeoJSONSourceSpecification, Map as MapLibreMap } from "maplibre-gl";

type GeoData = GeoJSONSourceSpecification["data"];

export interface MapLayerOptions {
  tileUrl: string;
  bounds: [number, number, number, number];
  localities?: GeoData;
  showLocalities: boolean;
  hotspots?: GeoData;
  showHotspots: boolean;
}

const HEAT = "heat";
const LOCALITIES = "localities";
const HOTSPOTS = "hotspots";

function removeLayerAndSource(map: MapLibreMap, id: string, layerIds: string[]): void {
  for (const layerId of layerIds) {
    if (map.getLayer(layerId)) map.removeLayer(layerId);
  }
  if (map.getSource(id)) map.removeSource(id);
}

/**
 * Keep the heat tiles, locality outlines and hotspot clusters in sync with the chosen options.
 * `styleVersion` changes whenever the base style (re)loads, which wipes custom layers, so they are re-added.
 * Overlays are inserted below the basemap's text labels so place names stay readable.
 */
export function useMapLayers(map: MapLibreMap | null, styleVersion: number, options: MapLayerOptions): void {
  const { tileUrl, bounds, localities, showLocalities, hotspots, showHotspots } = options;
  const [west, south, east, north] = bounds;

  useEffect(() => {
    if (!map || styleVersion === 0) return;
    const firstLabel = map.getStyle().layers?.find((layer) => layer.type === "symbol")?.id;
    removeLayerAndSource(map, HEAT, [HEAT]);
    map.addSource(HEAT, {
      type: "raster",
      tiles: [tileUrl],
      tileSize: 256,
      minzoom: 10,
      maxzoom: 16,
      bounds: [west, south, east, north],
    });
    map.addLayer({ id: HEAT, type: "raster", source: HEAT, paint: { "raster-opacity": 0.78, "raster-fade-duration": 150 } }, firstLabel);
    return () => {
      try {
        removeLayerAndSource(map, HEAT, [HEAT]);
      } catch {
        /* the map may already be destroyed */
      }
    };
  }, [map, styleVersion, tileUrl, west, south, east, north]);

  useEffect(() => {
    if (!map || styleVersion === 0 || !showLocalities || !localities) return;
    map.addSource(LOCALITIES, { type: "geojson", data: localities });
    map.addLayer({
      id: `${LOCALITIES}-line`,
      type: "line",
      source: LOCALITIES,
      paint: { "line-color": "#ffffff", "line-width": 1.2, "line-opacity": 0.85, "line-dasharray": [3, 2] },
    });
    return () => {
      try {
        removeLayerAndSource(map, LOCALITIES, [`${LOCALITIES}-line`]);
      } catch {
        /* the map may already be destroyed */
      }
    };
  }, [map, styleVersion, localities, showLocalities]);

  useEffect(() => {
    if (!map || styleVersion === 0 || !showHotspots || !hotspots) return;
    map.addSource(HOTSPOTS, { type: "geojson", data: hotspots });
    map.addLayer({
      id: `${HOTSPOTS}-fill`,
      type: "fill",
      source: HOTSPOTS,
      paint: {
        "fill-color": ["match", ["get", "cluster"], "hot", "#e0553a", "cold", "#3c6ec8", "#888888"],
        "fill-opacity": 0.3,
        "fill-outline-color": "#ffffff",
      },
    });
    return () => {
      try {
        removeLayerAndSource(map, HOTSPOTS, [`${HOTSPOTS}-fill`]);
      } catch {
        /* the map may already be destroyed */
      }
    };
  }, [map, styleVersion, hotspots, showHotspots]);
}
