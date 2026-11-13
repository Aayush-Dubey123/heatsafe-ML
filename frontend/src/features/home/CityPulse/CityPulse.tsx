import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useLocalities, useLocalitiesGeoJson } from "../../../api/queries/queries";
import { ErrorBlock, LoadingBlock } from "../../../components/status/StateViews/StateViews";
import { fmtTemp } from "../../../utils/format/format";
import { featureCenter } from "../../../utils/geo/geo";


interface CityPulseProps {
  /** Rows per list; use more when there is room so the panel is filled. */
  rows?: number;
  onPick: (lat: number, lon: number, name: string) => void;
}

interface Row {
  id: number;
  name: string;
  temp: number;
}

/** What the city looks like right now: the hottest and coolest localities, each one tap from its own answer. */
export function CityPulse({ onPick, rows: count = 5 }: CityPulseProps) {
  const { t } = useTranslation();
  const localities = useLocalities("latest_scene");
  const geo = useLocalitiesGeoJson();

  const centers = useMemo(() => {
    const map = new Map<number, { lat: number; lon: number }>();
    for (const feature of geo.data?.features ?? []) map.set(Number(feature.properties["locality_id"]), featureCenter(feature));
    return map;
  }, [geo.data]);

  const sorted = useMemo<Row[]>(
    () =>
      (localities.data ?? [])
        .filter((l) => l.mean_lst_celsius !== null && centers.has(l.locality_id))
        .map((l) => ({ id: l.locality_id, name: l.locality_name, temp: l.mean_lst_celsius as number }))
        .sort((a, b) => b.temp - a.temp),
    [localities.data, centers],
  );

  const renderList = (title: string, rows: Row[], tone: "hot" | "cool") => (
    <div className="stack" style={{ gap: 2, minWidth: 0, minHeight: 0 }}>
      <h3 style={{ fontSize: "var(--fs-md)" }}>{title}</h3>
      <ul style={{ listStyle: "none", margin: 0, padding: 0, flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
        {rows.map((row) => (
          <li key={row.id} style={{ flex: 1, maxHeight: 60, display: "flex" }}>
            <button
              type="button"
              className="btn"
              style={{ width: "100%", height: "100%", minHeight: 40, padding: "0 4px", gap: 6, justifyContent: "space-between", border: 0, borderBottom: "1px solid var(--border)", borderRadius: 0, background: "none", fontWeight: 400, fontSize: "var(--fs-sm)" }}
              aria-label={t("pulse.pick", { name: row.name })}
              onClick={() => {
                const center = centers.get(row.id);
                if (center) onPick(center.lat, center.lon, row.name);
              }}
            >
              <span>{row.name}</span>
              <span style={{ fontWeight: 600, color: tone === "hot" ? "var(--accent-text)" : "var(--info)" }}>{fmtTemp(row.temp)} °C</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );

  return (
    <section className="stack" aria-label={t("pulse.title")} style={{ gap: 10, height: "100%", minHeight: 0 }}>
      {(localities.isPending || geo.isPending) && <LoadingBlock lines={4} />}
      {localities.isError && <ErrorBlock error={localities.error} onRetry={() => void localities.refetch()} />}
      {sorted.length > 0 && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12, flex: 1, minHeight: 0 }}>
            {renderList(t("pulse.hottest"), sorted.slice(0, count), "hot")}
            {renderList(t("pulse.coolest"), sorted.slice(-count).reverse(), "cool")}
          </div>
          <p className="small muted">{t("pulse.note")}</p>
        </>
      )}
    </section>
  );
}
