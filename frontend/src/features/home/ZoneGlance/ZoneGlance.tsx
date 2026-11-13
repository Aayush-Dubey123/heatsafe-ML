import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useZones, useZonesGeoJson } from "../../../api/queries/queries";
import { ErrorBlock, LoadingBlock } from "../../../components/status/StateViews/StateViews";
import { fmtTemp } from "../../../utils/format/format";
import { ZoneMap } from "../../zones/ZoneMap/ZoneMap";
import { sortZones } from "../../zones/ZoneTable/ZoneTable";

const TOP = 3;

/** Small zone-risk map with the three highest-risk zones; one tap opens the full Zones page on that zone. */
export function ZoneGlance() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const zones = useZones("summer");
  const geo = useZonesGeoJson("summer");
  const open = (zoneId: number) => navigate({ pathname: "/zones", search: `?zone=${zoneId}` });

  return (
    <section className="card stack" aria-labelledby="glance-title" style={{ gap: 12 }}>
      <h2 id="glance-title" style={{ fontSize: "var(--fs-lg)" }}>{t("glance.title")}</h2>
      {(zones.isPending || geo.isPending) && <LoadingBlock lines={5} />}
      {zones.isError && <ErrorBlock error={zones.error} onRetry={() => void zones.refetch()} />}
      {zones.data && geo.data && (
        <>
          <ZoneMap collection={geo.data} metric="risk" metricLabel={t("zones.risk")} onSelect={open} />
          <div className="stack" style={{ gap: 4 }}>
            <h3 style={{ fontSize: "var(--fs-md)" }}>{t("glance.top")}</h3>
            <ol style={{ margin: 0, paddingLeft: 20 }}>
              {sortZones(zones.data, "risk").slice(0, TOP).map((zone) => (
                <li key={zone.zone_id} style={{ padding: "4px 0" }}>
                  <button type="button" onClick={() => open(zone.zone_id)} style={{ background: "none", border: 0, padding: 0, color: "var(--accent-text)", textDecoration: "underline", fontWeight: 500 }}>
                    {zone.zone_name}
                  </button>
                  <span className="muted"> · {fmtTemp(zone.risk_score)}</span>
                </li>
              ))}
            </ol>
          </div>
          <Link className="btn" to="/zones">{t("glance.seeAll")}</Link>
        </>
      )}
    </section>
  );
}
