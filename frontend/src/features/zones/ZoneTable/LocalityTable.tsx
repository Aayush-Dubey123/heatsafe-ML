import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { LocalitySummary } from "../../../api/types/types";
import { fmtTemp, isExposureLevel } from "../../../utils/format/format";
import styles from "./ZoneTable.module.css";

interface LocalityTableProps {
  localities: LocalitySummary[];
  centers: Map<number, { lat: number; lon: number }>;
  /** Rows per page; paging replaces scrolling so the list always fits the screen. */
  pageSize?: number;
}

/** The 55 named localities ordered by exposure (highest first); each links to the heat answer for that place. */
export function LocalityTable({ localities, centers, pageSize = 8 }: LocalityTableProps) {
  const { t } = useTranslation();
  const sorted = [...localities].sort((a, b) => (b.exposure_index ?? -Infinity) - (a.exposure_index ?? -Infinity));
  const pages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const [requested, setPage] = useState(0);
  const page = Math.min(requested, pages - 1);
  const rows = sorted.slice(page * pageSize, (page + 1) * pageSize);

  return (
    <>
    <table className={styles.table} style={{ height: "auto" }}>
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
                {isExposureLevel(row.exposure_level) && <span className={`small muted ${styles.lvl}`}> · {t(`level.${row.exposure_level}`)}</span>}
              </td>
              <td>{fmtTemp(row.area_km2, 1)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
    <div className={styles.pager}>
      <button type="button" className="btn" style={{ minHeight: 38 }} disabled={page === 0} onClick={() => setPage(page - 1)}>
        {t("zones.prev")}
      </button>
      <span className="small muted">{t("zones.pageOf", { page: page + 1, pages })}</span>
      <button type="button" className="btn" style={{ minHeight: 38 }} disabled={page >= pages - 1} onClick={() => setPage(page + 1)}>
        {t("zones.next")}
      </button>
    </div>
    </>
  );
}
