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
}

/** Nearest parks, water, health facilities and shelters, with distance and a link to open them on a map. */
export function CoolingList({ lat, lon }: CoolingListProps) {
  const { t } = useTranslation();
  const spots = useCoolingSpots(lat, lon);

  return (
    <section className="card stack" aria-labelledby="cooling-title" style={{ gap: 8 }}>
      <h2 id="cooling-title" style={{ fontSize: "var(--fs-lg)" }}>
        {t("cooling.title")}
      </h2>
      {spots.isPending && <LoadingBlock lines={3} />}
      {spots.isError && <ErrorBlock error={spots.error} onRetry={() => void spots.refetch()} />}
      {spots.data && spots.data.spots.length === 0 && <p className="muted">{t("cooling.none", { km: SEARCH_RADIUS_KM })}</p>}
      {spots.data && spots.data.spots.length > 0 && (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {spots.data.spots.map((spot) => {
            const category = spot.category as AssetCategory;
            const type = t(`cooling.${category}`);
            return (
              <li
                key={spot.asset_id}
                style={{ display: "flex", alignItems: "center", gap: 12, minHeight: 48, borderBottom: "1px solid var(--border)" }}
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
