import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useZones, useZonesGeoJson } from "../../../api/queries/queries";
import { ErrorBlock, LoadingBlock } from "../../../components/status/StateViews/StateViews";
import { fmtTemp } from "../../../utils/format/format";
import { ZoneMap } from "../../zones/ZoneMap/ZoneMap";
import { sortZones } from "../../zones/ZoneTable/ZoneTable";

const TOP = 3;

/** Zone-risk map that fills the space it is given, with the three highest-risk zones; a tap opens that zone. */
export function ZoneGlance() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const zones = useZones("summer");
  const geo = useZonesGeoJson("summer");
  const open = (zoneId: number) => navigate({ pathname: "/zones", search: `?zone=${zoneId}` });

  return (
    <section className="stack" aria-label={t("glance.title")} style={{ gap: 8, height: "100%", minHeight: 0 }}>
      {(zones.isPending || geo.isPending) && <LoadingBlock lines={5} />}
      {zones.isError && <ErrorBlock error={zones.error} onRetry={() => void zones.refetch()} />}
      {zones.data && geo.data && (
        <>
          <div style={{ flex: 1, minHeight: 0 }}>
            <ZoneMap collection={geo.data} metric="risk" metricLabel={t("zones.risk")} onSelect={open} fit />
          </div>
          <div className="row" style={{ gap: 6, flexWrap: "nowrap" }}>
            <span className="small muted" style={{ flex: "none" }}>{t("glance.top")}</span>
            {sortZones(zones.data, "risk").slice(0, TOP).map((zone) => (
              <button key={zone.zone_id} type="button" className="btn chip" style={{ minHeight: 36, padding: "0 10px", fontSize: "var(--fs-sm)" }} onClick={() => open(zone.zone_id)}>
                {zone.zone_name} · {fmtTemp(zone.risk_score, 0)}
              </button>
            ))}
            <Link className="btn" style={{ minHeight: 36, padding: "0 12px", marginLeft: "auto" }} to="/zones">{t("glance.seeAll")}</Link>
          </div>
        </>
      )}
    </section>
  );
}
