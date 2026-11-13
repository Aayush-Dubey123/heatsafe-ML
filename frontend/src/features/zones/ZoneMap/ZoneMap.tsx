import { useMemo } from "react";
import type { KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import type { AreaCollection } from "../../../api/endpoints/endpoints";
import { boundsOf, featureCenter, makeProjector, svgPath } from "../../../utils/geo/geo";

const WIDTH = 460;
const HEIGHT = 400;
/** Light to dark: low to high. The same colours as the heat scale tokens. */
const RAMP = ["#fbe88a", "#f4a43a", "#e0553a", "#8c2d6b", "#2a1a5e"] as const;

export type ZoneMetric = "risk" | "exposure" | "vulnerability";
export const METRIC_FIELD: Record<ZoneMetric, string> = {
  risk: "risk_score",
  exposure: "exposure_index",
  vulnerability: "vulnerability_score",
};

interface ZoneMapProps {
  collection: AreaCollection;
  metric: ZoneMetric;
  metricLabel: string;
  selectedId?: number;
  onSelect: (zoneId: number) => void;
  /** Fill the height of the parent instead of the natural height. */
  fit?: boolean;
}

function valueOf(properties: Record<string, unknown>, metric: ZoneMetric): number | null {
  const value = properties[METRIC_FIELD[metric]];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/**
 * Zone choropleth drawn as plain SVG: light and works offline, keyboard accessible.
 * Colours are relative (min to max among the zones), so they show ranking, not absolute heat.
 */
export function ZoneMap({ collection, metric, metricLabel, selectedId, onSelect, fit = false }: ZoneMapProps) {
  const { t } = useTranslation();
  const shapes = useMemo(() => {
    const project = makeProjector(boundsOf(collection.features), WIDTH, HEIGHT);
    const values = collection.features.map((f) => valueOf(f.properties, metric));
    const finite = values.filter((v): v is number => v !== null);
    const min = Math.min(...finite);
    const max = Math.max(...finite);
    return collection.features.map((feature, index) => {
      const value = values[index] ?? null;
      const bin = value === null || max === min ? 0 : Math.min(RAMP.length - 1, Math.floor(((value - min) / (max - min)) * RAMP.length));
      const center = featureCenter(feature);
      const [x, y] = project(center.lon, center.lat);
      return {
        id: Number(feature.properties["zone_id"]),
        name: String(feature.properties["zone_name"] ?? ""),
        path: svgPath(feature, project),
        fill: RAMP[bin] ?? RAMP[0],
        value,
        x,
        y,
        dark: bin >= 3,
      };
    });
  }, [collection, metric]);

  const onKey = (event: KeyboardEvent<SVGPathElement>, id: number) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect(id);
    }
  };

  return (
    <figure style={fit ? { margin: 0, height: "100%", minHeight: 0, display: "flex", flexDirection: "column" } : { margin: 0 }}>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} width="100%" style={fit ? { flex: 1, minHeight: 0 } : undefined} role="group" aria-label={t("zones.mapLabel", { metric: metricLabel })}>
        {shapes.map((shape) => (
          <path
            key={shape.id}
            d={shape.path}
            fill={shape.fill}
            stroke={shape.id === selectedId ? "var(--accent)" : "var(--surface)"}
            strokeWidth={shape.id === selectedId ? 3 : 1.5}
            strokeLinejoin="round"
            role="button"
            tabIndex={0}
            aria-pressed={shape.id === selectedId}
            aria-label={`${shape.name}: ${metricLabel} ${shape.value === null ? "–" : shape.value.toFixed(1)}`}
            style={{ cursor: "pointer" }}
            onClick={() => onSelect(shape.id)}
            onKeyDown={(event) => onKey(event, shape.id)}
          />
        ))}
        {shapes.map((shape) => (
          <text
            key={`label-${shape.id}`}
            x={shape.x}
            y={shape.y}
            textAnchor="middle"
            fontSize="11"
            pointerEvents="none"
            fill={shape.dark ? "#ffffff" : "#1b1b19"}
          >
            {shape.name}
          </text>
        ))}
      </svg>
      <figcaption className="small muted" style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span>{t("zones.lower")}</span>
        <span aria-hidden="true" style={{ flex: 1, display: "flex", height: 8, borderRadius: 2, overflow: "hidden" }}>
          {RAMP.map((color) => (
            <span key={color} style={{ flex: 1, background: color }} />
          ))}
        </span>
        <span>{t("zones.higher")}</span>
      </figcaption>
    </figure>
  );
}
