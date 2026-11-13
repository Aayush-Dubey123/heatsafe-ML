import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useHeat } from "../../../api/queries/queries";
import { ErrorBlock, LoadingBlock } from "../../../components/status/StateViews/StateViews";
import { Icon } from "../../../components/ui/Icon/Icon";
import { Tabs } from "../../../components/ui/Tabs/Tabs";
import type { TabItem } from "../../../components/ui/Tabs/Tabs";
import { useMediaQuery } from "../../../hooks/useMediaQuery/useMediaQuery";
import { locationSearch, useUrlState } from "../../../hooks/useUrlState/useUrlState";
import { AdviceHero } from "../AdviceHero/AdviceHero";
import { CityPulse } from "../CityPulse/CityPulse";
import { CoolTips } from "../CoolTips/CoolTips";
import { CoolingList } from "../CoolingList/CoolingList";
import { HeatCard } from "../HeatCard/HeatCard";
import { LocationPicker } from "../LocationPicker/LocationPicker";
import { ZoneGlance } from "../ZoneGlance/ZoneGlance";
import styles from "./HomePage.module.css";

/**
 * Answer-first home that fits the screen without scrolling. The answer for the chosen place sits on top;
 * everything else (details, seasons, cool places, the city, zones, tips) is one tap away in tabs.
 * On wide screens the cool places stay beside the answer and the other tabs fill the right column.
 */
export function HomePage() {
  const { t } = useTranslation();
  const { state, update } = useUrlState();
  const wide = useMediaQuery("(min-width: 900px)");
  const [changing, setChanging] = useState(false);
  const hasPoint = state.lat !== undefined && state.lon !== undefined;
  const heat = useHeat(state.lat, state.lon);

  const pick = (lat: number, lon: number, name?: string) => {
    update({ lat: lat.toFixed(5), lon: lon.toFixed(5), name });
    setChanging(false);
  };

  const placeName = state.name ?? heat.data?.locality?.name ?? (hasPoint ? `${state.lat?.toFixed(3)}, ${state.lon?.toFixed(3)}` : "");
  const search = locationSearch(state);
  const showAnswer = hasPoint && !changing;

  const cityTab: TabItem = { id: "city", label: t("tab.city"), content: <CityPulse onPick={pick} rows={wide ? 8 : 5} /> };
  const zonesTab: TabItem = { id: "zones", label: t("tab.zones"), content: <ZoneGlance /> };
  const tipsTab: TabItem = { id: "tips", label: t("tab.tips"), content: <CoolTips bare /> };
  const tabs: TabItem[] = [];
  if (hasPoint && heat.data?.covered && !wide) {
    tabs.push({ id: "now", label: t("tab.now"), content: <HeatCard heat={heat.data} compact showHeadline={false} bare /> });
    tabs.push({ id: "seasons", label: t("tab.seasons"), content: <HeatCard heat={heat.data} tableOnly bare /> });
  }
  if (hasPoint && state.lat !== undefined && state.lon !== undefined) {
    tabs.push({ id: "cool", label: t("tab.cool"), content: <CoolingList lat={state.lat} lon={state.lon} bare /> });
  }
  tabs.push(cityTab, zonesTab);
  if (hasPoint || !wide) tabs.push(tipsTab);

  const answer = (
    <>
      {showAnswer && (
        <div className="card" style={{ background: "var(--accent-bg)", borderColor: "transparent", padding: "10px 14px", display: "flex", flexDirection: "column", gap: 6 }}>
          <div className="row" style={{ justifyContent: "space-between", flexWrap: "nowrap", gap: 8 }}>
            <div className="row" style={{ gap: 6, flexWrap: "nowrap", minWidth: 0 }}>
              <Icon name="pin" size={16} />
              <h1 style={{ fontSize: "var(--fs-md)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{placeName}</h1>
            </div>
            <button type="button" className="btn" style={{ minHeight: 36, padding: "0 12px", flex: "none" }} onClick={() => setChanging(true)}>
              {t("home.change")}
            </button>
          </div>
          {heat.isPending && <LoadingBlock lines={3} />}
          {heat.isError && <ErrorBlock error={heat.error} onRetry={() => void heat.refetch()} />}
          <div aria-live="polite">{heat.data && <AdviceHero heat={heat.data} />}</div>
          {heat.data && !heat.data.covered && <HeatCard heat={heat.data} compact bare />}
        </div>
      )}
    </>
  );

  return (
    <div className={`page ${styles.grid}`}>
      <div className={styles.left}>
        {!showAnswer && (
          <>
            <header className="stack" style={{ gap: 6 }}>
              <h1 style={{ fontSize: "var(--fs-xl)" }}>{t("home.title")}</h1>
              <p className="muted">{t("home.intro")}</p>
            </header>
            <LocationPicker onPick={pick} />
          </>
        )}
        {answer}
        {showAnswer && wide && heat.data?.covered && (
          <div className={`card ${styles.cool}`}>
            <HeatCard heat={heat.data} showHeadline={false} bare />
          </div>
        )}
        {!hasPoint && wide && (
          <div className={`card ${styles.cool}`}>
            <h2 style={{ fontSize: "var(--fs-md)", marginBottom: 8 }}>{t("tips.title")}</h2>
            <CoolTips bare />
          </div>
        )}
        {showAnswer && !wide && heat.data && (
          <div className="row" style={{ flexWrap: "nowrap" }}>
            <Link className="btn btn-primary" style={{ flex: 1 }} to={{ pathname: "/map", search }}>
              <Icon name="map" /> {t("home.openMap")}
            </Link>
            <Link className="btn" style={{ flex: 1 }} to={{ pathname: "/zones", search }}>
              <Icon name="list" /> {t("home.hottestZones")}
            </Link>
          </div>
        )}
      </div>

      <div className={styles.right}>
        <Tabs key={`${hasPoint}-${wide}-${heat.data?.covered ?? "x"}`} tabs={tabs} label={t("home.title")} />
      </div>
    </div>
  );
}
