import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { absoluteTileUrl } from "../../../api/client/client";
import { useHeat, useHotspots, useLocalitiesGeoJson, useMetadata } from "../../../api/queries/queries";
import { ErrorBlock, LoadingBlock } from "../../../components/status/StateViews/StateViews";
import { locationSearch, useUrlState } from "../../../hooks/useUrlState/useUrlState";
import { HeatCard } from "../../home/HeatCard/HeatCard";
import { LocationPicker } from "../../home/LocationPicker/LocationPicker";
import { LayerChips, describeLayer } from "../LayerChips/LayerChips";
import { Legend } from "../LayerChips/Legend";
import { MapView } from "../MapView/MapView";
import styles from "./MapPage.module.css";

/** Map-first view: heat tiles over a basemap, layer chips, legend, and the heat card for the tapped spot. */
export function MapPage() {
  const { t } = useTranslation();
  const { state, update } = useUrlState();
  const metadata = useMetadata();
  const [showLocalities, setShowLocalities] = useState(false);
  const [showHotspots, setShowHotspots] = useState(false);

  const { kind, season } = describeLayer(state.layer);
  const heat = useHeat(state.lat, state.lon);
  const localities = useLocalitiesGeoJson();
  const hotspots = useHotspots(season ?? "summer", showHotspots);
  const layerInfo = metadata.data?.layers.find((layer) => layer.id === state.layer);
  const hasPoint = state.lat !== undefined && state.lon !== undefined;

  if (metadata.isPending) return <div className="page"><LoadingBlock lines={5} /></div>;
  if (metadata.isError || !metadata.data || !layerInfo) {
    return (
      <div className="page">
        <ErrorBlock error={metadata.error} onRetry={() => void metadata.refetch()} />
      </div>
    );
  }
  const [west = 78.9, south = 21, east = 79.3, north = 21.3] = metadata.data.bounds;

  return (
    <div className={styles.layout}>
      <div className={styles.mapArea}>
        <MapView
          bounds={[west, south, east, north]}
          tileUrl={absoluteTileUrl(layerInfo.tile_url)}
          center={hasPoint ? { lat: state.lat as number, lon: state.lon as number } : undefined}
          localities={localities.data as never}
          showLocalities={showLocalities}
          hotspots={hotspots.data as never}
          showHotspots={showHotspots}
          onPick={(lat, lon) => update({ lat: lat.toFixed(5), lon: lon.toFixed(5), name: undefined })}
        />
      </div>
      <aside className={`${styles.panel} stack`} aria-label={t("map.title")}>
        <h1 style={{ fontSize: "var(--fs-lg)" }}>{t("map.title")}</h1>
        <LayerChips value={state.layer} onChange={(layer) => update({ layer: layer === "latest_lst" ? undefined : layer }, true)} />
        <Legend kind={kind} vmin={layerInfo.vmin} vmax={layerInfo.vmax} />
        <div className="stack" style={{ gap: 4 }}>
          <label className="row small" style={{ gap: 8 }}>
            <input type="checkbox" checked={showLocalities} onChange={(event) => setShowLocalities(event.target.checked)} />
            {t("map.showLocalities")}
          </label>
          <label className="row small" style={{ gap: 8 }}>
            <input type="checkbox" checked={showHotspots} onChange={(event) => setShowHotspots(event.target.checked)} />
            {t("map.showHotspots")}
          </label>
        </div>
        <LocationPicker onPick={(lat, lon, name) => update({ lat: lat.toFixed(5), lon: lon.toFixed(5), name })} />
        {!hasPoint && <p className="small muted">{t("map.tapHint")}</p>}
        {hasPoint && heat.isPending && <LoadingBlock lines={3} />}
        {hasPoint && heat.isError && <ErrorBlock error={heat.error} onRetry={() => void heat.refetch()} />}
        <div aria-live="polite">{hasPoint && heat.data && <HeatCard heat={heat.data} compact />}</div>
        {hasPoint && heat.data && (
          <Link className="btn" to={{ pathname: "/", search: locationSearch(state) }}>
            {t("map.fullDetails")}
          </Link>
        )}
      </aside>
    </div>
  );
}
