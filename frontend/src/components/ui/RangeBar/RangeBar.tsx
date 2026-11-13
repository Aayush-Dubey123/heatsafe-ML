import { useTranslation } from "react-i18next";
import { fmtTemp } from "../../../utils/format/format";
import styles from "./RangeBar.module.css";

interface RangeBarProps {
  value: number;
  low: number;
  high: number;
}

/**
 * Shows the 90% range around the estimate on a small scale.
 * The scale is padded around the range so its width is readable; a screen reader gets the sentence instead.
 */
export function RangeBar({ value, low, high }: RangeBarProps) {
  const { t } = useTranslation();
  const lo = Math.min(low, value);
  const hi = Math.max(high, value);
  const min = lo - 3;
  const max = hi + 3;
  const pct = (v: number) => `${(((v - min) / (max - min)) * 100).toFixed(1)}%`;
  const label = t("heat.rangeAria", { value: fmtTemp(value), low: fmtTemp(low), high: fmtTemp(high) });

  return (
    <figure className={styles.figure} role="img" aria-label={label}>
      <div className={styles.track} aria-hidden="true">
        <div className={styles.range} style={{ left: pct(lo), width: `calc(${pct(hi)} - ${pct(lo)})` }} />
        <div className={styles.marker} style={{ left: pct(value) }} />
      </div>
      <figcaption className={styles.caption} aria-hidden="true">
        <span>{fmtTemp(low)}</span>
        <span>{t("heat.rangeLabel")}</span>
        <span>{fmtTemp(high)}</span>
      </figcaption>
    </figure>
  );
}
