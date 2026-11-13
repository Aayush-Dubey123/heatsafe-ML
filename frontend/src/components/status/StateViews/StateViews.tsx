import { useTranslation } from "react-i18next";
import { ApiError } from "../../../api/client/client";
import { Icon } from "../../ui/Icon/Icon";

/** Translation key explaining an error in plain words (never raw exception text). */
export function errorKey(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "network_error") return "state.network";
    if (error.code === "no_product_available") return "state.noProduct";
    if (error.code === "outside_study_area") return "state.outside";
    if (error.code === "rate_limited") return "state.rate";
  }
  return "state.generic";
}

/** Skeleton placeholder shown while data loads (keeps layout steady, no spinner in the middle). */
export function LoadingBlock({ lines = 3, label }: { lines?: number; label?: string }) {
  const { t } = useTranslation();
  return (
    <div className="stack" role="status" aria-live="polite" aria-busy="true" style={{ gap: 10 }}>
      <span className="sr-only">{label ?? t("state.loading")}</span>
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="skeleton" style={{ height: i === 0 ? 40 : 16, width: i === 0 ? "55%" : "90%" }} />
      ))}
    </div>
  );
}

interface ErrorBlockProps {
  error: unknown;
  onRetry?: () => void;
}

/** Friendly error with a retry button; an out-of-area answer is informational, not a failure. */
export function ErrorBlock({ error, onRetry }: ErrorBlockProps) {
  const { t } = useTranslation();
  const informational = error instanceof ApiError && error.code === "outside_study_area";
  return (
    <div className={`notice ${informational ? "notice-info" : "notice-danger"} stack`} role="alert" style={{ gap: 8 }}>
      <div className="row" style={{ gap: 8 }}>
        <Icon name={informational ? "info" : "alert"} />
        <strong>{informational ? t(errorKey(error)) : t("state.errorTitle")}</strong>
      </div>
      {!informational && <p>{t(errorKey(error))}</p>}
      {onRetry && !informational && (
        <button type="button" className="btn" onClick={onRetry} style={{ alignSelf: "flex-start" }}>
          {t("state.retry")}
        </button>
      )}
    </div>
  );
}
