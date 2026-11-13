import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { ZoneSummary } from "../../../api/types/types";
import { fmtNumber, fmtTemp, isExposureLevel } from "../../../utils/format/format";

interface ZoneDetailProps {
  zone: ZoneSummary;
  center?: { lat: number; lon: number };
}

/** Facts about one zone, with the uncertainty and data caveats spelled out next to the numbers. */
export function ZoneDetail({ zone, center }: ZoneDetailProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const assets = Object.entries(zone.assets ?? {}).filter(([, count]) => count > 0);
  const search = center ? `?lat=${center.lat.toFixed(5)}&lon=${center.lon.toFixed(5)}&name=${encodeURIComponent(zone.zone_name)}` : "";

  return (
    <section className="card stack" aria-labelledby="zone-detail-title" style={{ gap: 10 }}>
      <h2 id="zone-detail-title" style={{ fontSize: "var(--fs-lg)" }}>
        {zone.zone_name}
      </h2>
      <dl style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "6px 16px", margin: 0 }}>
        <dt className="muted">{t("zones.area")}</dt>
        <dd style={{ margin: 0 }}>{fmtTemp(zone.area_km2, 1)} km²</dd>
        <dt className="muted">{t("zones.population")}</dt>
        <dd style={{ margin: 0 }}>
          {t("zones.people", { n: fmtNumber(zone.population, locale) })}
          <span className="small muted" style={{ display: "block" }}>
            {t("zones.perKm2", { n: fmtNumber(zone.population_density_per_km2 === null ? null : Math.round(zone.population_density_per_km2), locale) })}
          </span>
        </dd>
        <dt className="muted">{t("zones.green")}</dt>
        <dd style={{ margin: 0 }}>
          {fmtTemp(zone.green_deficit, 2)}
          <span className="small muted" style={{ display: "block" }}>{t("zones.greenHelp")}</span>
        </dd>
        <dt className="muted">{t("zones.age60")}</dt>
        <dd style={{ margin: 0 }}>
          {zone.share_age_60_plus === null ? "–" : `${(zone.share_age_60_plus * 100).toFixed(1)}%`}
          <span className="small muted" style={{ display: "block" }}>{t("zones.age60Help")}</span>
        </dd>
        <dt className="muted">{t("zones.colExposure")}</dt>
        <dd style={{ margin: 0 }}>
          {fmtTemp(zone.exposure_index)}
          {isExposureLevel(zone.exposure_level) && <> · {t(`level.${zone.exposure_level}`)}</>}
          {zone.exposure_index_ci_low !== null && zone.exposure_index_ci_high !== null && (
            <span className="small muted" style={{ display: "block" }}>
              {t("zones.exposureCi", { low: fmtTemp(zone.exposure_index_ci_low), high: fmtTemp(zone.exposure_index_ci_high) })}
            </span>
          )}
        </dd>
      </dl>
      {assets.length > 0 && (
        <p className="small">
          <strong>{t("zones.assets")}: </strong>
          {assets.map(([category, count]) => `${t(`cooling.${category}`)} ${count}`).join(" · ")}
        </p>
      )}
      {center && (
        <Link className="btn" to={{ pathname: "/", search }}>
          {t("zones.viewOnMap")}
        </Link>
      )}
    </section>
  );
}
