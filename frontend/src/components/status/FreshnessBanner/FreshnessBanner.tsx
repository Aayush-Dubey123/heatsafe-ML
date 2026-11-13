import { useTranslation } from "react-i18next";
import type { ProductInfo } from "../../../api/types/types";
import { Icon } from "../../ui/Icon/Icon";

/** The age limit after which a satellite image counts as stale (Decision D2). */
export const STALE_AFTER_DAYS = 16;

interface FreshnessBannerProps {
  product?: ProductInfo;
  offline: boolean;
  noProduct?: boolean;
}

/**
 * Honest status line shown above every page: offline, no data yet, or data older than the limit.
 * Renders nothing when everything is fine.
 */
export function FreshnessBanner({ product, offline, noProduct = false }: FreshnessBannerProps) {
  const { t } = useTranslation();
  if (offline) {
    return (
      <div className="notice notice-info row" role="status">
        <Icon name="offline" /> {t("banner.offline")}
      </div>
    );
  }
  if (noProduct) {
    return (
      <div className="notice notice-warn row" role="status">
        <Icon name="alert" /> {t("banner.noProduct")}
      </div>
    );
  }
  if (product?.stale) {
    return (
      <div className="notice notice-warn row" role="status">
        <Icon name="alert" /> {t("banner.stale", { days: product.scene_age_days, limit: STALE_AFTER_DAYS })}
      </div>
    );
  }
  return null;
}
