import { useTranslation } from "react-i18next";

/** Colour stops of the colour maps used to render the tiles (matplotlib "inferno" and "magma"). */
const STOPS = {
  temp: ["#000004", "#420a68", "#932667", "#dd513a", "#fca50a", "#fcffa4"],
  exposure: ["#000004", "#3b0f70", "#8c2981", "#de4968", "#fe9f6d", "#fcfdbf"],
} as const;

interface LegendProps {
  kind: "temp" | "exposure";
  vmin: number;
  vmax: number;
}

/** Colour scale for the active map layer, with its unit and the honest meaning of the numbers. */
export function Legend({ kind, vmin, vmax }: LegendProps) {
  const { t } = useTranslation();
  return (
    <figure style={{ margin: 0 }} aria-label={kind === "temp" ? t("map.legendTemp") : t("map.legendExposure")}>
      <div
        aria-hidden="true"
        style={{ height: 10, borderRadius: 3, background: `linear-gradient(to right, ${STOPS[kind].join(", ")})` }}
      />
      <figcaption className="small muted" style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
        <span>{vmin}</span>
        <span>{kind === "temp" ? t("map.legendTemp") : t("map.legendExposure")}</span>
        <span>{vmax}</span>
      </figcaption>
    </figure>
  );
}
