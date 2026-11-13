import { useId, useMemo, useState } from "react";
import type { KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { useLocalitiesGeoJson } from "../../../api/queries/queries";
import { Icon } from "../../../components/ui/Icon/Icon";
import { useGeolocation } from "../../../hooks/useDevice/useDevice";
import { featureCenter } from "../../../utils/geo/geo";
import styles from "./LocationPicker.module.css";

interface LocationPickerProps {
  onPick: (lat: number, lon: number, name?: string) => void;
  /** "pill" is the compact floating search used on the map: one rounded field with a locate button inside. */
  variant?: "form" | "pill";
}

interface Place {
  name: string;
  lat: number;
  lon: number;
}

const MAX_RESULTS = 8;

/** Choose a place by searching the 55 locality names or by using the device location. */
export function LocationPicker({ onPick, variant = "form" }: LocationPickerProps) {
  const pill = variant === "pill";
  const { t } = useTranslation();
  const id = useId();
  const listId = `${id}-list`;
  const localities = useLocalitiesGeoJson();
  const { status, locate } = useGeolocation();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);

  const places = useMemo<Place[]>(
    () =>
      (localities.data?.features ?? [])
        .map((feature) => ({ name: String(feature.properties["locality_name"] ?? ""), ...featureCenter(feature) }))
        .filter((place) => place.name !== "")
        .sort((a, b) => a.name.localeCompare(b.name)),
    [localities.data],
  );

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (needle === "") return [];
    return places.filter((place) => place.name.toLowerCase().includes(needle)).slice(0, MAX_RESULTS);
  }, [places, query]);

  const choose = (place: Place) => {
    setQuery("");
    setOpen(false);
    onPick(place.lat, place.lon, place.name);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActive((index) => Math.min(index + 1, matches.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      const place = matches[active];
      if (place) {
        event.preventDefault();
        choose(place);
      }
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  };

  const showList = open && query.trim() !== "";
  const statusMessage = { denied: "home.denied", unavailable: "home.unavailable", failed: "home.failed", locating: "home.locating" }[
    status as "denied" | "unavailable" | "failed" | "locating"
  ];

  return (
    <div className="stack" style={{ gap: 12 }}>
      <div className={styles.search}>
        <label htmlFor={`${id}-input`} className={pill ? "sr-only" : "small muted"}>
          {t("home.searchLabel")}
        </label>
        <div className={pill ? `${styles.field} ${styles.pill}` : styles.field}>
          <Icon name="search" />
          <input
            id={`${id}-input`}
            type="search"
            role="combobox"
            autoComplete="off"
            aria-expanded={showList}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={showList && matches[active] ? `${id}-opt-${active}` : undefined}
            placeholder={t("home.searchPlaceholder")}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setActive(0);
              setOpen(true);
            }}
            onKeyDown={onKeyDown}
            onBlur={() => setOpen(false)}
          />
          {pill && (
            <button
              type="button"
              className={styles.locate}
              onClick={() => locate((lat, lon) => onPick(lat, lon))}
              disabled={status === "locating"}
              aria-label={t("home.useLocation")}
              title={t("home.useLocation")}
            >
              <Icon name="locate" size={20} />
            </button>
          )}
        </div>
        {showList && (
          <ul id={listId} role="listbox" className={styles.list}>
            {matches.length === 0 ? (
              <li className={styles.empty}>{t("home.noResults", { query: query.trim() })}</li>
            ) : (
              matches.map((place, index) => (
                <li
                  key={place.name}
                  id={`${id}-opt-${index}`}
                  role="option"
                  aria-selected={index === active}
                  className={index === active ? styles.activeOption : styles.option}
                  onMouseDown={(event) => {
                    event.preventDefault();
                    choose(place);
                  }}
                >
                  <Icon name="pin" size={16} /> {place.name}
                </li>
              ))
            )}
          </ul>
        )}
      </div>
      {!pill && (
        <button
          type="button"
          className="btn"
          onClick={() => locate((lat, lon) => onPick(lat, lon))}
          disabled={status === "locating"}
        >
          <Icon name="locate" /> {t("home.useLocation")}
        </button>
      )}
      <div role="status" className={pill && statusMessage ? "notice notice-warn small" : "small muted"}>
        {statusMessage ? t(statusMessage) : null}
      </div>
    </div>
  );
}
