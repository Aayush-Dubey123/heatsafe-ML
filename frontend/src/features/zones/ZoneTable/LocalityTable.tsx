import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { LocalitySummary } from "../../../api/types/types";
import { fmtTemp, isExposureLevel } from "../../../utils/format/format";
import styles from "./ZoneTable.module.css";

interface LocalityTableProps {
  localities: LocalitySummary[];
  centers: Map<number, { lat: number; lon: number }>;
}

/** The 55 named localities ordered by exposure (highest first); each links to the heat answer for that place. */
export function LocalityTable({ localities, centers }: LocalityTableProps) {
  const { t } = useTranslation();
  const rows = [...localities].sort((a, b) => (b.exposure_index ?? -Infinity) - (a.exposure_index ?? -Infinity));

  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th scope="col">{t("zones.colLocality")}</th>
          <th scope="col">{t("zones.colMeanLst")}</th>
          <th scope="col">{t("zones.colExposure")}</th>
          <th scope="col">{t("zones.colArea")}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const center = centers.get(row.locality_id);
          const search = center
            ? `?lat=${center.lat.toFixed(5)}&lon=${center.lon.toFixed(5)}&name=${encodeURIComponent(row.locality_name)}`
            : "";
          return (
            <tr key={row.locality_id}>
              <th scope="row">
                {center ? <Link to={{ pathname: "/", search }}>{row.locality_name}</Link> : row.locality_name}
                {row.in_extended_limit && <span className="small muted"> · {t("zones.extendedLimit")}</span>}
              </th>
              <td>{fmtTemp(row.mean_lst_celsius)}</td>
              <td>
                {fmtTemp(row.exposure_index)}
                {isExposureLevel(row.exposure_level) && <span className="small muted"> · {t(`level.${row.exposure_level}`)}</span>}
              </td>
              <td>{fmtTemp(row.area_km2, 1)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
