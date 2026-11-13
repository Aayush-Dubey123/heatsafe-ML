import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ApiError } from "../../../api/client/client";
import { useMetadata } from "../../../api/queries/queries";
import { locationSearch, useUrlState } from "../../../hooks/useUrlState/useUrlState";
import { useOnline } from "../../../hooks/useDevice/useDevice";
import { FreshnessBanner } from "../../status/FreshnessBanner/FreshnessBanner";
import { Icon } from "../../ui/Icon/Icon";
import type { IconName } from "../../ui/Icon/Icon";
import { LanguageSwitch } from "../../ui/LanguageSwitch/LanguageSwitch";
import styles from "./Shell.module.css";

const TABS: { to: string; key: string; icon: IconName; end?: boolean }[] = [
  { to: "/", key: "nav.home", icon: "home", end: true },
  { to: "/map", key: "nav.map", icon: "map" },
  { to: "/zones", key: "nav.zones", icon: "list" },
  { to: "/about", key: "nav.about", icon: "info" },
];

/** App frame: header with language switch, status banner, page content, persistent disclaimer, mobile tab bar. */
export function Shell() {
  const { t } = useTranslation();
  const online = useOnline();
  const { state } = useUrlState();
  const metadata = useMetadata();
  const search = locationSearch(state);
  const noProduct =
    metadata.error instanceof ApiError && metadata.error.code === "no_product_available" && !metadata.data;

  return (
    <div className={styles.frame}>
      <a className="skip-link" href="#main">
        {t("app.skip")}
      </a>
      <header className={styles.header}>
        <div className={styles.brand}>
          <span className={styles.logo} aria-hidden="true" />
          <span>{t("app.name")}</span>
        </div>
        <nav className={styles.nav} aria-label={t("nav.primary")}>
          {TABS.map((tab) => (
            <NavLink
              key={tab.to}
              to={{ pathname: tab.to, search }}
              end={tab.end}
              className={({ isActive }) => `${styles.tab} ${isActive ? styles.active : ""}`}
            >
              <Icon name={tab.icon} size={20} />
              <span>{t(tab.key)}</span>
            </NavLink>
          ))}
        </nav>
        <LanguageSwitch />
      </header>
      <div className={styles.banner}>
        <FreshnessBanner product={metadata.data?.product} offline={!online} noProduct={noProduct} />
      </div>
      <main id="main" className={styles.main} tabIndex={-1}>
        <Outlet />
      </main>
      <footer className={styles.footer}>
        <p>{t("disclaimer.short")}</p>
        <p>{t("disclaimer.advisory")}</p>
      </footer>
    </div>
  );
}
