import { useTranslation } from "react-i18next";
import { useCoolingSpots } from "../../../api/queries/queries";
import type { AssetCategory, HeatResponse } from "../../../api/types/types";
import { Icon } from "../../../components/ui/Icon/Icon";
import { fmtDistance } from "../../../utils/format/format";
import { directionsLink } from "../../../utils/geo/geo";

/** Plain-language band for the ground temperature (surface, not air) so the answer reads like advice. */
export function adviceKey(lstCelsius: number): "mild" | "warm" | "hot" | "veryHot" {
  if (lstCelsius < 30) return "mild";
  if (lstCelsius < 36) return "warm";
  if (lstCelsius < 42) return "hot";
  return "veryHot";
}

interface AdviceHeroProps {
  heat: HeatResponse;
  place?: string;
}

/**
 * The first thing people read: a friendly headline, the temperature with its likely range,
 * and the nearest place to cool down with a directions link.
 */
export function AdviceHero({ heat, place }: AdviceHeroProps) {
  const { t } = useTranslation();
  const cooling = useCoolingSpots(heat.latitude, heat.longitude);
  if (!heat.covered || heat.lst_celsius === null) return null;

  const low = heat.lst_p05 ?? heat.lst_celsius;
  const high = heat.lst_p95 ?? heat.lst_celsius;
  const nearest = cooling.data?.spots[0];
  const nearestName = nearest ? (nearest.name ?? t("cooling.unnamed", { type: t(`cooling.${nearest.category as AssetCategory}`) })) : "";

  return (
    <section
      aria-label={t(`advice.${adviceKey(heat.lst_celsius)}`)}
      className="stack"
      style={{ gap: 6, padding: "2px" }}
    >
      {place && <p className="small muted row" style={{ gap: 4 }}><Icon name="pin" size={14} /> {place}</p>}
      <h2 data-collapsible="true" style={{ fontSize: "var(--fs-lg)", lineHeight: 1.2 }}>{t(`advice.${adviceKey(heat.lst_celsius)}`)}</h2>
      <p style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
        <span style={{ fontSize: "var(--fs-hero)", fontWeight: 650, lineHeight: 1, color: "var(--accent-text)" }}>
          {Math.round(heat.lst_celsius)} °C
        </span>
        <span className="muted">{t("heat.rangeShort", { low: Math.round(low), high: Math.round(high) })}</span>
      </p>
      {nearest && (
        <div className="row" data-collapsible="true" style={{ gap: 8, flexWrap: "nowrap", background: "var(--ok-bg)", color: "var(--ok-text)", borderRadius: "var(--radius-sm)", padding: "6px 8px 6px 12px" }}>
          <Icon name="tree" size={20} />
          <span className="small" style={{ flex: 1, minWidth: 0 }}>{t("advice.nearest", { name: nearestName, distance: fmtDistance(nearest.distance_km) })}</span>
          <a
            className="btn"
            aria-label={t("advice.directions")}
            style={{ minHeight: 40, padding: "0 12px", flex: "none" }}
            href={directionsLink(nearest.latitude, nearest.longitude)}
            target="_blank"
            rel="noopener noreferrer"
          >
            <Icon name="route" size={18} /> <span className="sr-only">{t("advice.directions")}</span>
          </a>
        </div>
      )}
    </section>
  );
}
