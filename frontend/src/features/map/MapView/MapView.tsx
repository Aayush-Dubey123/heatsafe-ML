import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { COOLING_LAYER, useMapLayers } from "./useMapLayers";
import type { MapLayerOptions } from "./useMapLayers";
import { ZoomDock } from "../ZoomDock/ZoomDock";
import type { ZoomableMap } from "../ZoomDock/ZoomDock";
import styles from "./MapView.module.css";

/** Free, light vector basemap (OpenFreeMap Positron, no key): muted so the heat colours stand out. If it cannot load we fall back to plain OpenStreetMap tiles. */
const BASEMAP_STYLE = "https://tiles.openfreemap.org/styles/positron";
const FALLBACK_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      maxzoom: 19,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};
const STYLE_TIMEOUT_MS = 8000;

interface MapViewProps extends MapLayerOptions {
  center?: { lat: number; lon: number };
  onPick: (lat: number, lon: number) => void;
  /** Called with the asset id when a cooling-place pin is tapped. */
  onSpot?: (assetId: string) => void;
}

/** Interactive map: basemap, heat tile overlay, optional outlines/clusters, and a marker for the chosen spot. */
export function MapView({ center, onPick, onSpot, ...layerOptions }: MapViewProps) {
  const { t } = useTranslation();
  const container = useRef<HTMLDivElement>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const onPickRef = useRef(onPick);
  const onSpotRef = useRef(onSpot);
  const [map, setMap] = useState<maplibregl.Map | null>(null);
  const [styleVersion, setStyleVersion] = useState(0);
  const [failed, setFailed] = useState(false);
  const { bounds } = layerOptions;

  useEffect(() => {
    onPickRef.current = onPick;
    onSpotRef.current = onSpot;
  }, [onPick, onSpot]);

  useEffect(() => {
    const element = container.current;
    if (!element) return;
    let instance: maplibregl.Map;
    try {
      instance = new maplibregl.Map({
        container: element,
        style: BASEMAP_STYLE,
        bounds,
        fitBoundsOptions: { padding: 16 },
        minZoom: 9,
        maxZoom: 17,
        attributionControl: { compact: true },
      });
    } catch {
      setFailed(true);
      return;
    }
    let loadedOnce = false;
    let usedFallback = false;
    const switchToFallback = () => {
      if (loadedOnce || usedFallback) return;
      usedFallback = true;
      instance.setStyle(FALLBACK_STYLE);
    };
    const timer = window.setTimeout(switchToFallback, STYLE_TIMEOUT_MS);
    instance.on("style.load", () => {
      loadedOnce = true;
      setStyleVersion((version) => version + 1);
    });
    instance.on("error", (event) => {
      if (String(event.error?.message ?? "").toLowerCase().includes("webgl")) setFailed(true);
      else switchToFallback();
    });
    instance.on("click", (event) => {
      if (instance.getLayer(COOLING_LAYER)) {
        const pin = instance.queryRenderedFeatures(event.point, { layers: [COOLING_LAYER] })[0];
        if (pin) {
          onSpotRef.current?.(String(pin.properties?.["asset_id"] ?? ""));
          return;
        }
      }
      onPickRef.current(event.lngLat.lat, event.lngLat.lng);
    });
    instance.on("mousemove", (event) => {
      const overPin = instance.getLayer(COOLING_LAYER) && instance.queryRenderedFeatures(event.point, { layers: [COOLING_LAYER] }).length > 0;
      instance.getCanvas().style.cursor = overPin ? "pointer" : "";
    });
    setMap(instance);
    return () => {
      window.clearTimeout(timer);
      markerRef.current?.remove();
      markerRef.current = null;
      instance.remove();
      setMap(null);
      setStyleVersion(0);
    };
    // The map is created once; later bounds changes do not need a new map.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useMapLayers(map, styleVersion, { ...layerOptions });

  const lat = center?.lat;
  const lon = center?.lon;
  useEffect(() => {
    if (!map || lat === undefined || lon === undefined) return;
    markerRef.current?.remove();
    markerRef.current = new maplibregl.Marker({ color: "#c4471d" }).setLngLat([lon, lat]).addTo(map);
    map.easeTo({ center: [lon, lat], zoom: Math.max(map.getZoom(), 13), duration: 600 });
  }, [map, lat, lon]);

  if (failed) {
    return (
      <div className={styles.fallback} role="alert">
        {t("map.unavailable")}
      </div>
    );
  }
  return (
    <div className={styles.wrap}>
      <div ref={container} className={styles.map} role="region" aria-label={t("map.ariaLabel")} />
      {map && <ZoomDock map={map as unknown as ZoomableMap} bounds={bounds} spot={center} />}
    </div>
  );
}
