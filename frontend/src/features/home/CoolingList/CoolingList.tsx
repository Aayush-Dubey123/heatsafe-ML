import { useTranslation } from "react-i18next";
import { useCoolingSpots } from "../../../api/queries/queries";
import type { AssetCategory } from "../../../api/types/types";
import { Icon } from "../../../components/ui/Icon/Icon";
import type { IconName } from "../../../components/ui/Icon/Icon";
import { ErrorBlock, LoadingBlock } from "../../../components/status/StateViews/StateViews";
import { fmtDistance } from "../../../utils/format/format";
import { osmPlaceLink } from "../../../utils/geo/geo";

const ICONS: Record<AssetCategory, IconName> = {
  green_space: "tree",
  water_body: "drop",
  health_facility: "hospital",
  public_shelter: "shelter",
  drinking_water: "drop",
};

const SEARCH_RADIUS_KM = 5;

interface CoolingListProps {
  lat: number;
  lon: number;
  /** Most places to list (the rest are on the map). */
  limit?: number;
  /** Drop the card chrome and title so it can sit inside a tab. */
  bare?: boolean;
}

/** Nearest parks, water, health facilities and shelters, with distance and a link to open them on a map. */
export function CoolingList({ lat, lon, limit = 5, bare = false }: CoolingListProps) {
  const { t } = useTranslation();
  const spots = useCoolingSpots(lat, lon);

  return (
    <section className={bare ? "stack" : "card stack"} aria-labelledby="cooling-title" style={bare ? { gap: 8, height: "100%", minHeight: 0 } : { gap: 8 }}>
      <h2 id="cooling-title" style={{ fontSize: "var(--fs-lg)" }} className={bare ? "sr-only" : undefined}>
        {t("cooling.title")}
      </h2>
      {spots.isPending && <LoadingBlock lines={3} />}
      {spots.isError && <ErrorBlock error={spots.error} onRetry={() => void spots.refetch()} />}
      {spots.data && spots.data.spots.length === 0 && <p className="muted">{t("cooling.none", { km: SEARCH_RADIUS_KM })}</p>}
      {spots.data && spots.data.spots.length > 0 && (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, ...(bare ? { flex: 1, minHeight: 0, display: "flex", flexDirection: "column" } : {}) }}>
          {spots.data.spots.slice(0, limit).map((spot) => {
            const category = spot.category as AssetCategory;
            const type = t(`cooling.${category}`);
            return (
              <li
                key={spot.asset_id}
                style={{ display: "flex", alignItems: "center", gap: 12, minHeight: 44, borderBottom: "1px solid var(--border)", ...(bare ? { flex: 1, maxHeight: 80 } : {}) }}
              >
                <Icon name={ICONS[category] ?? "pin"} size={20} />
                <span style={{ flex: 1 }}>
                  {spot.name ?? t("cooling.unnamed", { type })}
                  <span className="small muted" style={{ display: "block" }}>
                    {spot.name ? `${type} · ` : ""}
                    {t("cooling.away", { distance: fmtDistance(spot.distance_km) })}
                  </span>
                </span>
                <a
                  href={osmPlaceLink(spot.latitude, spot.longitude)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="small"
                  aria-label={`${t("cooling.openMap")}: ${spot.name ?? type}`}
                >
                  <Icon name="external" size={16} />
                </a>
              </li>
            );
          })}
        </ul>
      )}
      <p className="small muted">{t("cooling.source")}</p>
    </section>
  );
}
