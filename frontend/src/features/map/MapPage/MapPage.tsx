import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { absoluteTileUrl } from "../../../api/client/client";
import { useCoolingSpots, useHeat, useHotspots, useLocalitiesGeoJson, useMetadata } from "../../../api/queries/queries";
import type { AssetCategory } from "../../../api/types/types";
import { ErrorBlock, LoadingBlock } from "../../../components/status/StateViews/StateViews";
import { BottomSheet } from "../../../components/ui/BottomSheet/BottomSheet";
import { Icon } from "../../../components/ui/Icon/Icon";
import { Tabs } from "../../../components/ui/Tabs/Tabs";
import { locationSearch, useUrlState } from "../../../hooks/useUrlState/useUrlState";
import { fmtDistance } from "../../../utils/format/format";
import { directionsLink } from "../../../utils/geo/geo";
import { AdviceHero } from "../../home/AdviceHero/AdviceHero";
import { CoolingList } from "../../home/CoolingList/CoolingList";
import { HeatCard } from "../../home/HeatCard/HeatCard";
import { LocationPicker } from "../../home/LocationPicker/LocationPicker";
import { LayerChips, describeLayer } from "../LayerChips/LayerChips";
import { Legend } from "../LayerChips/Legend";
import { MapView } from "../MapView/MapView";
import styles from "./MapPage.module.css";

/**
 * Map-first view: full-bleed map with a floating search pill and layer chips, cooling-place pins,
 * and a bottom sheet (side panel on desktop) holding the answer for the chosen spot.
 */
export function MapPage() {
  const { t } = useTranslation();
  const { state, update } = useUrlState();
  const metadata = useMetadata();
  const [showLocalities, setShowLocalities] = useState(false);
  const [showHotspots, setShowHotspots] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [spotId, setSpotId] = useState<string>();
  const [sheetTab, setSheetTab] = useState("details");

  const { kind, season } = describeLayer(state.layer);
  const heat = useHeat(state.lat, state.lon);
  const cooling = useCoolingSpots(state.lat, state.lon);
  const localities = useLocalitiesGeoJson();
  const hotspots = useHotspots(season ?? "summer", showHotspots);
  const layerInfo = metadata.data?.layers.find((layer) => layer.id === state.layer);
  const hasPoint = state.lat !== undefined && state.lon !== undefined;

  const pins = useMemo(
    () =>
      cooling.data
        ? {
            type: "FeatureCollection" as const,
            features: cooling.data.spots.map((spot) => ({
              type: "Feature" as const,
              geometry: { type: "Point" as const, coordinates: [spot.longitude, spot.latitude] },
              properties: { asset_id: spot.asset_id, category: spot.category },
            })),
          }
        : undefined,
    [cooling.data],
  );
  const spot = cooling.data?.spots.find((candidate) => candidate.asset_id === spotId);

  if (metadata.isPending) return <div className="page"><LoadingBlock lines={5} /></div>;
  if (metadata.isError || !metadata.data || !layerInfo) {
    return (
      <div className="page">
        <ErrorBlock error={metadata.error} onRetry={() => void metadata.refetch()} />
      </div>
    );
  }
  const [west = 78.9, south = 21, east = 79.3, north = 21.3] = metadata.data.bounds;
  const pick = (lat: number, lon: number, name?: string) => {
    setSpotId(undefined);
    update({ lat: lat.toFixed(5), lon: lon.toFixed(5), name });
  };
  const placeName = state.name ?? heat.data?.locality?.name;

  return (
    <div className={styles.stage}>
      <div className={styles.mapArea}>
        <MapView
          bounds={[west, south, east, north]}
          tileUrl={absoluteTileUrl(layerInfo.tile_url)}
          center={hasPoint ? { lat: state.lat as number, lon: state.lon as number } : undefined}
          localities={localities.data as never}
          showLocalities={showLocalities}
          hotspots={hotspots.data as never}
          showHotspots={showHotspots}
          cooling={pins as never}
          selectedSpot={spotId}
          onPick={(lat, lon) => pick(lat, lon)}
          onSpot={(id) => {
            setSpotId(id);
            setSheetTab("places");
            setExpanded(true);
          }}
        />
      </div>

      <div className={styles.top}>
        <LocationPicker variant="pill" onPick={pick} />
        <LayerChips value={state.layer} onChange={(layer) => update({ layer: layer === "latest_lst" ? undefined : layer }, true)} />
      </div>

      <BottomSheet
        expanded={expanded}
        onExpandedChange={setExpanded}
        label={t("map.title")}
        summary={
          <div aria-live="polite">
            {!hasPoint && <p className="muted" style={{ paddingTop: 4 }}>{t("map.tapHint")}</p>}
            {hasPoint && heat.isPending && <LoadingBlock lines={3} />}
            {hasPoint && heat.isError && <ErrorBlock error={heat.error} onRetry={() => void heat.refetch()} />}
            {hasPoint && heat.data && <AdviceHero heat={heat.data} place={placeName} />}
            {hasPoint && heat.data && !heat.data.covered && <HeatCard heat={heat.data} compact />}
          </div>
        }
      >
        <Tabs
          label={t("map.title")}
          value={sheetTab}
          onChange={setSheetTab}
          tabs={[
            {
              id: "details",
              label: t("tab.details"),
              content: (
                <div className="stack" style={{ gap: 10 }}>
                  {hasPoint && heat.data?.covered && <HeatCard heat={heat.data} compact showHeadline={false} bare hidePlace />}
                  {hasPoint && heat.data && (
                    <Link className="btn" to={{ pathname: "/", search: locationSearch(state) }}>
                      {t("map.fullDetails")}
                    </Link>
                  )}
                  {!hasPoint && <p className="muted">{t("map.tapHint")}</p>}
                </div>
              ),
            },
            {
              id: "places",
              label: t("tab.places"),
              content: (
                <div className="stack" style={{ gap: 10 }}>
                  {spot && (
                    <div className="row" style={{ gap: 10, flexWrap: "nowrap", background: "var(--ok-bg)", color: "var(--ok-text)", borderRadius: "var(--radius-sm)", padding: "8px 8px 8px 12px" }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <p style={{ fontWeight: 600 }}>{spot.name ?? t("cooling.unnamed", { type: t(`cooling.${spot.category as AssetCategory}`) })}</p>
                        <p className="small">
                          {t(`cooling.${spot.category as AssetCategory}`)} · {t("cooling.away", { distance: fmtDistance(spot.distance_km) })}
                        </p>
                      </div>
                      <a className="btn btn-primary" style={{ flex: "none", minHeight: 40 }} href={directionsLink(spot.latitude, spot.longitude)} target="_blank" rel="noopener noreferrer">
                        <Icon name="route" size={16} /> {t("cooling.directions")}
                      </a>
                    </div>
                  )}
                  {hasPoint && state.lat !== undefined && state.lon !== undefined ? (
                    <CoolingList lat={state.lat} lon={state.lon} bare />
                  ) : (
                    <p className="muted">{t("map.tapHint")}</p>
                  )}
                </div>
              ),
            },
            {
              id: "layers",
              label: t("tab.layers"),
              content: (
                <div className="stack" style={{ gap: 12 }}>
                  <Legend kind={kind} vmin={layerInfo.vmin} vmax={layerInfo.vmax} />
                  <div className="row" style={{ gap: 16 }}>
                    <label className="row small" style={{ gap: 8 }}>
                      <input type="checkbox" checked={showLocalities} onChange={(event) => setShowLocalities(event.target.checked)} />
                      {t("map.showLocalities")}
                    </label>
                    <label className="row small" style={{ gap: 8 }}>
                      <input type="checkbox" checked={showHotspots} onChange={(event) => setShowHotspots(event.target.checked)} />
                      {t("map.showHotspots")}
                    </label>
                  </div>
                  <p className="small muted">{t("disclaimer.short")} {t("disclaimer.advisory")}</p>
                  <p className="small muted">{t("map.credits")}</p>
                </div>
              ),
            },
          ]}
        />
      </BottomSheet>
    </div>
  );
}
