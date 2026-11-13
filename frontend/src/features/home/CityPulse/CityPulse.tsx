import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useLocalities, useLocalitiesGeoJson } from "../../../api/queries/queries";
import { ErrorBlock, LoadingBlock } from "../../../components/status/StateViews/StateViews";
import { fmtTemp } from "../../../utils/format/format";
import { featureCenter } from "../../../utils/geo/geo";

const ROWS = 4;

interface CityPulseProps {
  onPick: (lat: number, lon: number, name: string) => void;
}

interface Row {
  id: number;
  name: string;
  temp: number;
}

/** What the city looks like right now: the hottest and coolest localities, each one tap from its own answer. */
export function CityPulse({ onPick }: CityPulseProps) {
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
    <div className="stack" style={{ gap: 4 }}>
      <h3 style={{ fontSize: "var(--fs-md)" }}>{title}</h3>
      <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {rows.map((row) => (
          <li key={row.id}>
            <button
              type="button"
              className="btn"
              style={{ width: "100%", justifyContent: "space-between", border: 0, borderBottom: "1px solid var(--border)", borderRadius: 0, background: "none", fontWeight: 400 }}
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
    <section className="card stack" aria-labelledby="pulse-title" style={{ gap: 12 }}>
      <h2 id="pulse-title" style={{ fontSize: "var(--fs-lg)" }}>{t("pulse.title")}</h2>
      {(localities.isPending || geo.isPending) && <LoadingBlock lines={4} />}
      {localities.isError && <ErrorBlock error={localities.error} onRetry={() => void localities.refetch()} />}
      {sorted.length > 0 && (
        <>
          {renderList(t("pulse.hottest"), sorted.slice(0, ROWS), "hot")}
          {renderList(t("pulse.coolest"), sorted.slice(-ROWS).reverse(), "cool")}
          <p className="small muted">{t("pulse.note")}</p>
        </>
      )}
    </section>
  );
}
