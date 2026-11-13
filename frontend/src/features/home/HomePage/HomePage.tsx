import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useHeat } from "../../../api/queries/queries";
import { ErrorBlock, LoadingBlock } from "../../../components/status/StateViews/StateViews";
import { Icon } from "../../../components/ui/Icon/Icon";
import { locationSearch, useUrlState } from "../../../hooks/useUrlState/useUrlState";
import { AdviceHero } from "../AdviceHero/AdviceHero";
import { CoolingList } from "../CoolingList/CoolingList";
import { HeatCard } from "../HeatCard/HeatCard";
import { LocationPicker } from "../LocationPicker/LocationPicker";

/** Answer-first home: pick a place, then see how hot it is, how sure we are, and where to cool down. */
export function HomePage() {
  const { t } = useTranslation();
  const { state, update } = useUrlState();
  const [changing, setChanging] = useState(false);
  const hasPoint = state.lat !== undefined && state.lon !== undefined;
  const heat = useHeat(state.lat, state.lon);

  const pick = (lat: number, lon: number, name?: string) => {
    update({ lat: lat.toFixed(5), lon: lon.toFixed(5), name });
    setChanging(false);
  };

  const placeName = state.name ?? heat.data?.locality?.name ?? (hasPoint ? `${state.lat?.toFixed(3)}, ${state.lon?.toFixed(3)}` : "");
  const search = locationSearch(state);

  return (
    <div className="page stack" style={{ maxWidth: 720 }}>
      {!hasPoint && (
        <header className="stack" style={{ gap: 8 }}>
          <h1 style={{ fontSize: "var(--fs-xl)" }}>{t("home.title")}</h1>
          <p className="muted">{t("home.intro")}</p>
        </header>
      )}

      {(!hasPoint || changing) && <LocationPicker onPick={pick} />}

      {hasPoint && !changing && (
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div className="row" style={{ gap: 8 }}>
            <Icon name="pin" />
            <div>
              <p className="small muted">{t("home.yourPlace")}</p>
              <h1 style={{ fontSize: "var(--fs-lg)" }}>{placeName}</h1>
            </div>
          </div>
          <button type="button" className="btn" onClick={() => setChanging(true)}>
            {t("home.change")}
          </button>
        </div>
      )}

      {hasPoint && heat.isPending && <LoadingBlock lines={4} />}
      {hasPoint && heat.isError && <ErrorBlock error={heat.error} onRetry={() => void heat.refetch()} />}
      <div aria-live="polite" className="stack">
        {hasPoint && heat.data && (
          <div className="card" style={{ background: "var(--accent-bg)", borderColor: "transparent" }}>
            <AdviceHero heat={heat.data} />
          </div>
        )}
        {hasPoint && heat.data && <HeatCard heat={heat.data} showHeadline={false} />}
      </div>

      {hasPoint && heat.data && state.lat !== undefined && state.lon !== undefined && (
        <>
          <CoolingList lat={state.lat} lon={state.lon} />
          <div className="row">
            <Link className="btn btn-primary" to={{ pathname: "/map", search }}>
              <Icon name="map" /> {t("home.openMap")}
            </Link>
            <Link className="btn" to={{ pathname: "/zones", search }}>
              <Icon name="list" /> {t("home.hottestZones")}
            </Link>
          </div>
        </>
      )}
    </div>
  );
}
