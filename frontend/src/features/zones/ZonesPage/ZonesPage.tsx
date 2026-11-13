import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocalities, useLocalitiesGeoJson, useZones, useZonesGeoJson } from "../../../api/queries/queries";
import { METRIC_LAYERS, SEASONS } from "../../../api/types/types";
import type { MetricLayer, Season } from "../../../api/types/types";
import { ErrorBlock, LoadingBlock } from "../../../components/status/StateViews/StateViews";
import { useUrlState } from "../../../hooks/useUrlState/useUrlState";
import { featureCenter } from "../../../utils/geo/geo";
import { LocalityTable } from "../ZoneTable/LocalityTable";
import { ZoneDetail } from "../ZoneDetail/ZoneDetail";
import { ZoneMap } from "../ZoneMap/ZoneMap";
import type { ZoneMetric } from "../ZoneMap/ZoneMap";
import { ZoneTable } from "../ZoneTable/ZoneTable";

type View = "zones" | "localities";

/** Planner view: ranked zones with intervals and a choropleth, or the 55 localities by exposure. */
export function ZonesPage() {
  const { t } = useTranslation();
  const { state, update } = useUrlState();
  const [view, setView] = useState<View>("zones");
  const [metric, setMetric] = useState<ZoneMetric>("risk");

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

  return (
    <div className="page stack">
      <h1 style={{ fontSize: "var(--fs-xl)" }}>{t("zones.title")}</h1>

      <div className="row" style={{ gap: 12 }}>
        <div role="group" aria-label={t("zones.title")} className="row" style={{ gap: 6 }}>
          {(["zones", "localities"] as const).map((option) => (
            <button key={option} type="button" className="btn" aria-pressed={view === option} onClick={() => setView(option)}>
              {option === "zones" ? t("zones.viewZones") : t("zones.viewLocalities")}
            </button>
          ))}
        </div>
        <label className="row small" style={{ gap: 8 }}>
          {t("zones.season")}
          <select
            value={view === "zones" ? state.season : state.metricLayer}
            onChange={(event) => update(view === "zones" ? { season: event.target.value } : { metric: event.target.value }, true)}
            style={{ minHeight: 44, padding: "0 8px", background: "var(--surface)", border: "1px solid var(--border-strong)", borderRadius: 6 }}
          >
            {seasonOptions.map((option) => (
              <option key={option} value={option}>
                {t(`season.${option}`)}
              </option>
            ))}
          </select>
        </label>
        {view === "zones" && (
          <div role="group" aria-label={t("zones.rankBy")} className="row" style={{ gap: 6 }}>
            <span className="small muted">{t("zones.rankBy")}</span>
            {(["risk", "exposure", "vulnerability"] as const).map((option) => (
              <button key={option} type="button" className="btn" aria-pressed={metric === option} onClick={() => setMetric(option)}>
                {t(`zones.${option}`)}
              </button>
            ))}
          </div>
        )}
      </div>

      {view === "zones" ? (
        <>
          <div className="notice notice-warn">{t("zones.approx")}</div>
          {(zones.isPending || zonesGeo.isPending) && <LoadingBlock lines={6} />}
          {zones.isError && <ErrorBlock error={zones.error} onRetry={() => void zones.refetch()} />}
          {zones.data && zonesGeo.data && (
            <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", alignItems: "start" }}>
              <div className="card" style={{ overflowX: "auto" }}>
                <ZoneTable zones={zones.data} metric={metric} selectedId={state.zone} onSelect={(zone) => update({ zone }, true)} />
                <p className="small muted" style={{ marginTop: 8 }}>{t("zones.intervalNote")}</p>
              </div>
              <div className="stack">
                <div className="card">
                  <ZoneMap
                    collection={zonesGeo.data}
                    metric={metric}
                    metricLabel={metricLabel}
                    selectedId={state.zone}
                    onSelect={(zone) => update({ zone }, true)}
                  />
                </div>
                {selected ? <ZoneDetail zone={selected} center={zoneCenter} /> : <p className="muted">{t("zones.selectPrompt")}</p>}
              </div>
            </div>
          )}
        </>
      ) : (
        <>
          <p className="small muted">{t("zones.localityNote")}</p>
          {localities.isPending && <LoadingBlock lines={6} />}
          {localities.isError && <ErrorBlock error={localities.error} onRetry={() => void localities.refetch()} />}
          {localities.data && (
            <div className="card" style={{ overflowX: "auto" }}>
              <LocalityTable localities={localities.data} centers={centers} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
