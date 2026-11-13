import { useTranslation } from "react-i18next";
import { SEASONS } from "../../../api/types/types";
import type { Season, TileLayerId } from "../../../api/types/types";

type Kind = "temp" | "exposure";

/** Split a tile layer id into its kind (temperature or exposure) and season (undefined for the latest scene). */
export function describeLayer(layer: TileLayerId): { kind: Kind; season?: Season } {
  if (layer === "latest_lst") return { kind: "temp" };
  const [prefix, ...rest] = layer.split("_");
  return { kind: prefix === "exposure" ? "exposure" : "temp", season: rest.join("_") as Season };
}

/** Build the tile layer id for a kind and season; the latest scene exists only as temperature. */
export function layerFor(kind: Kind, season?: Season): TileLayerId {
  if (kind === "temp" && season === undefined) return "latest_lst";
  const chosen = season ?? "summer";
  return (kind === "temp" ? `lst_${chosen}` : `exposure_${chosen}`) as TileLayerId;
}

interface LayerChipsProps {
  value: TileLayerId;
  onChange: (layer: TileLayerId) => void;
}

/** Choose what the map shows: temperature or exposure, for the latest scene or a season. */
export function LayerChips({ value, onChange }: LayerChipsProps) {
  const { t } = useTranslation();
  const { kind, season } = describeLayer(value);

  return (
    <div style={{ display: "flex", gap: 8, overflowX: "auto", flexWrap: "nowrap", paddingBottom: 6, scrollbarWidth: "none" }}>
      <div role="group" aria-label={t("map.layers")} style={{ display: "flex", gap: 6, flex: "none" }}>
        {(["temp", "exposure"] as const).map((option) => (
          <button
            key={option}
            type="button"
            className="btn chip"
            aria-pressed={kind === option}
            onClick={() => onChange(layerFor(option, option === "exposure" ? (season ?? "summer") : season))}
          >
            {option === "temp" ? t("map.kindTemp") : t("map.kindExposure")}
          </button>
        ))}
      </div>
      <div role="group" aria-label={t("zones.season")} style={{ display: "flex", gap: 6, flex: "none" }}>
        {kind === "temp" && (
          <button type="button" className="btn chip" aria-pressed={season === undefined} onClick={() => onChange("latest_lst")}>
            {t("season.latest_scene")}
          </button>
        )}
        {SEASONS.map((option) => (
          <button
            key={option}
            type="button"
            className="btn chip"
            aria-pressed={season === option}
            onClick={() => onChange(layerFor(kind, option))}
          >
            {t(`season.${option}`)}
          </button>
        ))}
      </div>
    </div>
  );
}
