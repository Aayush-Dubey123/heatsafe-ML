import { useTranslation } from "react-i18next";
import type { ZoneSummary } from "../../../api/types/types";
import { fmtRank, fmtTemp, isExposureLevel } from "../../../utils/format/format";
import type { ZoneMetric } from "../ZoneMap/ZoneMap";
import styles from "./ZoneTable.module.css";

/** Order zones by the chosen metric (highest first; for risk, by the published rank). */
export function sortZones(zones: ZoneSummary[], metric: ZoneMetric): ZoneSummary[] {
  const key = {
    risk: (z: ZoneSummary) => -(z.risk_score ?? -Infinity),
    exposure: (z: ZoneSummary) => -(z.exposure_index ?? -Infinity),
    vulnerability: (z: ZoneSummary) => -(z.vulnerability_score ?? -Infinity),
  }[metric];
  return [...zones].sort((a, b) => key(a) - key(b));
}

interface ZoneTableProps {
  zones: ZoneSummary[];
  metric: ZoneMetric;
  selectedId?: number;
  onSelect: (zoneId: number) => void;
}

/** Ranked zone table. Risk rank shows its 95% interval; overlapping intervals mean no clear difference. */
export function ZoneTable({ zones, metric, selectedId, onSelect }: ZoneTableProps) {
  const { t } = useTranslation();
  const rows = sortZones(zones, metric);

  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th scope="col">{t("zones.colRank")}</th>
          <th scope="col">{t("zones.colZone")}</th>
          <th scope="col">{t("zones.colRisk")}</th>
          <th scope="col">{t("zones.colExposure")}</th>
          <th scope="col">{t("zones.colVuln")}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((zone, index) => (
          <tr key={zone.zone_id} className={zone.zone_id === selectedId ? styles.selected : undefined}>
            <td>{metric === "risk" ? fmtRank(zone.risk_rank, zone.risk_rank_low, zone.risk_rank_high) : index + 1}</td>
            <th scope="row">
              <button
                type="button"
                className={styles.link}
                aria-pressed={zone.zone_id === selectedId}
                onClick={() => onSelect(zone.zone_id)}
              >
                {zone.zone_name}
              </button>
            </th>
            <td>{fmtTemp(zone.risk_score)}</td>
            <td>
              {fmtTemp(zone.exposure_index)}
              {isExposureLevel(zone.exposure_level) && <span className={`small muted ${styles.lvl}`}> · {t(`level.${zone.exposure_level}`)}</span>}
            </td>
            <td>{fmtTemp(zone.vulnerability_score)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
