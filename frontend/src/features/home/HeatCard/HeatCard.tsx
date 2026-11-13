import { useTranslation } from "react-i18next";
import type { HeatResponse } from "../../../api/types/types";
import { SEASONS } from "../../../api/types/types";
import { RangeBar } from "../../../components/ui/RangeBar/RangeBar";
import { fmtTemp, isExposureLevel } from "../../../utils/format/format";
import styles from "./HeatCard.module.css";

interface HeatCardProps {
  heat: HeatResponse;
  /** Compact layout for the map side panel: skips the seasonal table. */
  compact?: boolean;
  /** Show the big number and its range sentence; turn off when a hero above already shows them. */
  showHeadline?: boolean;
}

/**
 * The answer to "how hot is it here": estimate with its 90% range, whether the satellite saw the spot,
 * how old the image is, and how this place compares across seasons. It always says this is surface temperature.
 */
export function HeatCard({ heat, compact = false, showHeadline = true }: HeatCardProps) {
  const { t, i18n } = useTranslation();
  const { product } = heat;
  const date = new Intl.DateTimeFormat(i18n.language, { day: "numeric", month: "short", year: "numeric" }).format(
    new Date(`${product.scene_date}T00:00:00`),
  );
  const level = (code: string | null | undefined) => (isExposureLevel(code) ? t(`level.${code}`) : "–");
  const summer = heat.seasons["summer"];

  const place = [
    heat.locality ? t("heat.inLocality", { name: heat.locality.name }) : null,
    heat.zone ? t("heat.inZone", { name: heat.zone.name }) : null,
  ].filter(Boolean);

  if (!heat.covered || heat.lst_celsius === null) {
    return (
      <section className={`card stack ${styles.card}`} aria-label={t("heat.surface")}>
        {place.length > 0 && <p className="small muted">{place.join(" · ")}</p>}
        <p role="status">{t("heat.notCovered")}</p>
      </section>
    );
  }

  const low = heat.lst_p05 ?? heat.lst_celsius;
  const high = heat.lst_p95 ?? heat.lst_celsius;
  const sceneKey = product.scene_age_days === 0 ? "heat.sceneToday" : "heat.scene";

  return (
    <section className={`card stack ${styles.card}`} aria-label={t("heat.surface")}>
      {place.length > 0 && <p className="small muted">{place.join(" · ")}</p>}
      <div>
        <p className="small muted">{t("heat.surface")}</p>
        {showHeadline && (
          <p className={styles.headline}>
            <span className={styles.value} aria-hidden="true">
              {Math.round(heat.lst_celsius)} °C
            </span>
            <span className="muted">{t("heat.rangeShort", { low: Math.round(low), high: Math.round(high) })}</span>
          </p>
        )}
        <RangeBar value={heat.lst_celsius} low={low} high={high} />
      </div>

      <div className="row" style={{ gap: 8 }}>
        <span className={`badge ${heat.observed ? "badge-ok" : "badge-warn"}`}>
          {heat.observed ? t("heat.observed") : t("heat.filled")}
        </span>
        <span className="badge">{t(sceneKey, { date, days: product.scene_age_days })}</span>
      </div>
      {!heat.observed && <p className="small muted">{t("heat.filledHelp", { date })}</p>}

      {summer?.exposure_index != null && (
        <p className={styles.exposure}>
          {t("heat.exposureLine", { pct: Math.round(summer.exposure_index), level: level(summer.exposure_level).toLowerCase() })}
        </p>
      )}

      {!compact && (
        <table className={styles.table}>
          <caption className="small muted">{t("heat.seasonsTitle")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("heat.colSeason")}</th>
              <th scope="col">{t("heat.colMean")}</th>
              <th scope="col">{t("heat.colExposure")}</th>
            </tr>
          </thead>
          <tbody>
            {SEASONS.map((season) => {
              const row = heat.seasons[season];
              return (
                <tr key={season}>
                  <th scope="row">{t(`season.${season}`)}</th>
                  <td>{fmtTemp(row?.mean_lst_celsius)}</td>
                  <td>{level(row?.exposure_level)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      <p className="small muted">{t("heat.airNote")}</p>
    </section>
  );
}
