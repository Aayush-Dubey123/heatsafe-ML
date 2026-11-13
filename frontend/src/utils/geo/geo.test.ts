import { describe, expect, it } from "vitest";
import type { AreaFeature } from "../../api/types/types";
import { boundsOf, featureCenter, makeProjector, outerRings, ringArea, ringCentroid, svgPath } from "./geo";

const square: number[][] = [[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]];
const feature = (type: "Polygon" | "MultiPolygon", coordinates: unknown): AreaFeature =>
  ({ type: "Feature", properties: {}, geometry: { type, coordinates } }) as unknown as AreaFeature;

describe("geo", () => {
  it("computes ring area and centroid", () => {
    expect(ringArea(square)).toBe(4);
    expect(ringCentroid(square)).toEqual([1, 1]);
  });

  it("handles degenerate rings", () => {
    const [x, y] = ringCentroid([[1, 1], [3, 3], [1, 1]]);
    expect(Number.isFinite(x) && Number.isFinite(y)).toBe(true);
  });

  it("picks the centre of the largest piece of a multipolygon", () => {
    const multi = feature("MultiPolygon", [[square], [[[10, 10], [10.1, 10], [10.1, 10.1], [10, 10.1], [10, 10]]]]);
    expect(outerRings(multi)).toHaveLength(2);
    expect(featureCenter(multi)).toEqual({ lat: 1, lon: 1 });
  });

  it("finds bounds across features", () => {
    const a = feature("Polygon", [square]);
    const b = feature("Polygon", [[[5, -1], [6, -1], [6, 0], [5, 0], [5, -1]]]);
    expect(boundsOf([a, b])).toEqual([0, -1, 6, 2]);
  });

  it("projects inside the box with north up", () => {
    const project = makeProjector([0, 0, 2, 2], 100, 100, 10);
    const [xw, yn] = project(0, 2);
    const [xe, ys] = project(2, 0);
    expect(xe).toBeGreaterThan(xw);
    expect(ys).toBeGreaterThan(yn);
    for (const v of [xw, yn, xe, ys]) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(100);
    }
  });

  it("builds closed SVG path data", () => {
    const path = svgPath(feature("Polygon", [square]), makeProjector([0, 0, 2, 2], 100, 100));
    expect(path.startsWith("M")).toBe(true);
    expect(path.endsWith("Z")).toBe(true);
  });
});
