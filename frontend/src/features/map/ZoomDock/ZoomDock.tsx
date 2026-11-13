import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "../../../components/ui/Icon/Icon";
import styles from "./ZoomDock.module.css";

/** The few map methods the dock needs (MapLibre's Map satisfies this), so it can be tested without WebGL. */
export interface ZoomableMap {
  getZoom(): number;
  zoomTo(zoom: number, options?: { duration?: number }): unknown;
  zoomIn(): unknown;
  zoomOut(): unknown;
  fitBounds(bounds: [number, number, number, number], options?: { padding?: number }): unknown;
  flyTo(options: { center: [number, number]; zoom: number }): unknown;
  on(type: "zoom", listener: () => void): unknown;
  off(type: "zoom", listener: () => void): unknown;
}

interface ZoomDockProps {
  map: ZoomableMap;
  bounds: [number, number, number, number];
  spot?: { lat: number; lon: number };
  minZoom?: number;
  maxZoom?: number;
}

/** Word for how close the map is, so the slider position means something. */
export function zoomBand(zoom: number): "zoomCity" | "zoomArea" | "zoomStreet" {
  if (zoom < 11.5) return "zoomCity";
  if (zoom < 14) return "zoomArea";
  return "zoomStreet";
}

/**
 * Zoom without pinching or dragging: big plus and minus, a vertical slider that moves the map live,
 * and one-tap jumps to the whole city or the selected spot.
 */
export function ZoomDock({ map, bounds, spot, minZoom = 9, maxZoom = 17 }: ZoomDockProps) {
  const { t } = useTranslation();
  const [zoom, setZoom] = useState(() => map.getZoom());

  useEffect(() => {
    const sync = () => setZoom(map.getZoom());
    map.on("zoom", sync);
    sync();
    return () => {
      map.off("zoom", sync);
    };
  }, [map]);

  const band = t(`map.${zoomBand(zoom)}`);

  return (
    <div className={styles.dock} role="group" aria-label={t("map.zoomLabel")}>
      <button type="button" className={styles.btn} onClick={() => map.zoomIn()} aria-label={t("map.zoomIn")} disabled={zoom >= maxZoom - 0.01}>
        <span aria-hidden="true" className={styles.sign}>+</span>
      </button>
      <input
        type="range"
        className={styles.slider}
        min={minZoom}
        max={maxZoom}
        step={0.1}
        value={Math.min(maxZoom, Math.max(minZoom, zoom))}
        aria-label={t("map.zoomLabel")}
        aria-valuetext={band}
        onChange={(event) => map.zoomTo(Number(event.target.value), { duration: 0 })}
      />
      <button type="button" className={styles.btn} onClick={() => map.zoomOut()} aria-label={t("map.zoomOut")} disabled={zoom <= minZoom + 0.01}>
        <span aria-hidden="true" className={styles.sign}>−</span>
      </button>
      <span className={styles.band}>{band}</span>
      <button type="button" className={styles.btn} onClick={() => map.fitBounds(bounds, { padding: 16 })} aria-label={t("map.zoomFit")} title={t("map.zoomFit")}>
        <Icon name="map" size={20} />
      </button>
      {spot && (
        <button
          type="button"
          className={`${styles.btn} ${styles.spotBtn}`}
          onClick={() => map.flyTo({ center: [spot.lon, spot.lat], zoom: 15 })}
          aria-label={t("map.zoomSpot")}
          title={t("map.zoomSpot")}
        >
          <Icon name="pin" size={20} />
        </button>
      )}
    </div>
  );
}
