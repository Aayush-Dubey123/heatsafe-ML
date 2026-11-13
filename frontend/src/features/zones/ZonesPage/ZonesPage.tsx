import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocalities, useLocalitiesGeoJson, useZones, useZonesGeoJson } from "../../../api/queries/queries";
import { METRIC_LAYERS, SEASONS } from "../../../api/types/types";
import type { MetricLayer, Season } from "../../../api/types/types";
import { ErrorBlock, LoadingBlock } from "../../../components/status/StateViews/StateViews";
import { Tabs } from "../../../components/ui/Tabs/Tabs";
import { useFitRows } from "../../../hooks/useFitRows/useFitRows";
import { useMediaQuery } from "../../../hooks/useMediaQuery/useMediaQuery";
import { useUrlState } from "../../../hooks/useUrlState/useUrlState";
import { featureCenter } from "../../../utils/geo/geo";
import { LocalityTable } from "../ZoneTable/LocalityTable";
import { ZoneDetail } from "../ZoneDetail/ZoneDetail";
import { ZoneMap } from "../ZoneMap/ZoneMap";
import type { ZoneMetric } from "../ZoneMap/ZoneMap";
import { ZoneTable } from "../ZoneTable/ZoneTable";
import styles from "./ZonesPage.module.css";

type View = "zones" | "localities";

/**
 * Planner view that fits one screen: ranked zones with intervals, a choropleth and the chosen zone's facts
 * (side by side on wide screens, in tabs on phones), or the localities with paging instead of scrolling.
 */
export function ZonesPage() {
  const { t } = useTranslation();
  const { state, update } = useUrlState();
  const wide = useMediaQuery("(min-width: 900px)");
  const [view, setView] = useState<View>("zones");
  const [metric, setMetric] = useState<ZoneMetric>("risk");
  const [tab, setTab] = useState("ranking");
  const fit = useFitRows(30, 150);

  const zones = useZones(state.season);
  const zonesGeo = useZonesGeoJson(state.season);
  const localities = useLocalities(state.metricLayer);
  const localitiesGeo = useLocalitiesGeoJson();

  const selected = zones.data?.find((zone) => zone.zone_id === state.zone);
  const centers = useMemo(() => {
    const map = new Map<number, { lat: number; lon: number }>();
    for (const feature of localitiesGeo.data?.features ?? []) map.set(Number(feature.properties["locality_id"]), featureCenter(feature));
    return map;
  }, [localitiesGeo.data]);
  const zoneCenter = useMemo(() => {
    const feature = zonesGeo.data?.features.find((f) => Number(f.properties["zone_id"]) === state.zone);
    return feature ? featureCenter(feature) : undefined;
  }, [zonesGeo.data, state.zone]);

  const metricLabel = t(`zones.${metric}`);
  const seasonOptions: readonly (Season | MetricLayer)[] = view === "zones" ? SEASONS : METRIC_LAYERS;
  const select = (zone: number) => {
    update({ zone }, true);
    setTab("details");
  };

  const table =
    zones.data && (
      <div style={{ display: "flex", flexDirection: "column", gap: 6, height: "100%", minHeight: 0 }}>
        <div style={{ flex: 1, minHeight: 0 }}>
          <ZoneTable zones={zones.data} metric={metric} selectedId={state.zone} onSelect={select} />
        </div>
        <p className="small muted">{t("zones.approx")} {t("zones.intervalNote")}</p>
      </div>
    );
  const map = zonesGeo.data && (
    <ZoneMap collection={zonesGeo.data} metric={metric} metricLabel={metricLabel} selectedId={state.zone} onSelect={select} fit />
  );
  const detail = selected ? <ZoneDetail zone={selected} center={zoneCenter} /> : <p className="muted">{t("zones.selectPrompt")}</p>;

  return (
    <div className="page">
      <div className="row" style={{ gap: 8, flex: "none" }}>
        <h1 className="sr-only">{t("zones.title")}</h1>
        <div role="group" aria-label={t("zones.title")} className="row" style={{ gap: 6, flexWrap: "nowrap" }}>
          {(["zones", "localities"] as const).map((option) => (
            <button key={option} type="button" className="btn chip" aria-pressed={view === option} onClick={() => setView(option)}>
              {option === "zones" ? t("zones.viewZones") : t("zones.viewLocalities")}
            </button>
          ))}
        </div>
        <label className="row small" style={{ gap: 6, flexWrap: "nowrap" }}>
          {t("zones.season")}
          <select
            value={view === "zones" ? state.season : state.metricLayer}
            onChange={(event) => update(view === "zones" ? { season: event.target.value } : { metric: event.target.value }, true)}
            style={{ minHeight: 38, padding: "0 8px", background: "var(--surface)", border: "1px solid var(--border-strong)", borderRadius: "var(--radius-pill)" }}
          >
            {seasonOptions.map((option) => (
              <option key={option} value={option}>
                {t(`season.${option}`)}
              </option>
            ))}
          </select>
        </label>
        {view === "zones" && (
          <label className="row small" style={{ gap: 6, flexWrap: "nowrap" }}>
            {t("zones.rankBy")}
            <select
              value={metric}
              onChange={(event) => setMetric(event.target.value as ZoneMetric)}
              style={{ minHeight: 38, padding: "0 8px", background: "var(--surface)", border: "1px solid var(--border-strong)", borderRadius: "var(--radius-pill)" }}
            >
              {(["risk", "exposure", "vulnerability"] as const).map((option) => (
                <option key={option} value={option}>
                  {t(`zones.${option}`)}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {view === "zones" ? (
        <div className="fill" style={{ display: "flex", flexDirection: "column" }}>
          {(zones.isPending || zonesGeo.isPending) && <LoadingBlock lines={6} />}
          {zones.isError && <ErrorBlock error={zones.error} onRetry={() => void zones.refetch()} />}
          {zones.data && zonesGeo.data &&
            (wide ? (
              <div className={styles.cols}>
                <div className={`card ${styles.cell}`}>{table}</div>
                <div className={styles.side}>
                  <div className={`card ${styles.mapCard}`}>{map}</div>
                  <div className={styles.detail}>{detail}</div>
                </div>
              </div>
            ) : (
              <Tabs
                label={t("zones.title")}
                value={tab}
                onChange={setTab}
                tabs={[
                  { id: "ranking", label: t("tab.ranking"), content: table },
                  { id: "map", label: t("nav.map"), content: <div style={{ height: "100%" }}>{map}</div> },
                  { id: "details", label: t("tab.details"), content: detail },
                ]}
              />
            ))}
        </div>
      ) : (
        <div className="fill" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <p className="small muted">{t("zones.localityNote")}</p>
          {localities.isPending && <LoadingBlock lines={6} />}
          {localities.isError && <ErrorBlock error={localities.error} onRetry={() => void localities.refetch()} />}
          {localities.data && (
            <div ref={fit.ref} className={`card ${styles.cell}`} style={{ flex: 1 }}>
              <LocalityTable localities={localities.data} centers={centers} pageSize={fit.rows} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
