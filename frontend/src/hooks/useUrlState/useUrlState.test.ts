import { describe, expect, it } from "vitest";
import { locationSearch, parseUrlState } from "./useUrlState";

const parse = (query: string) => parseUrlState(new URLSearchParams(query));

describe("parseUrlState", () => {
  it("uses defaults for an empty URL", () => {
    expect(parse("")).toMatchObject({ layer: "latest_lst", season: "summer", metricLayer: "latest_scene" });
    expect(parse("").lat).toBeUndefined();
  });

  it("accepts a valid point and name", () => {
    expect(parse("lat=21.15&lon=79.07&name=Dhantoli")).toMatchObject({ lat: 21.15, lon: 79.07, name: "Dhantoli" });
  });

  it("drops points outside the study area or with only one coordinate", () => {
    expect(parse("lat=40&lon=79.07").lat).toBeUndefined();
    expect(parse("lat=21.15").lat).toBeUndefined();
    expect(parse("lat=abc&lon=79.07").lon).toBeUndefined();
  });

  it("ignores unknown layers and seasons", () => {
    const state = parse("layer=evil&season=spring&metric=x");
    expect(state).toMatchObject({ layer: "latest_lst", season: "summer", metricLayer: "latest_scene" });
  });

  it("limits the name length and validates the zone id", () => {
    expect(parse(`lat=21.1&lon=79&name=${"a".repeat(200)}`).name).toHaveLength(60);
    expect(parse("zone=4").zone).toBe(4);
    expect(parse("zone=-1").zone).toBeUndefined();
    expect(parse("zone=1.5").zone).toBeUndefined();
  });
});

describe("locationSearch", () => {
  it("round-trips a place and is empty without one", () => {
    expect(locationSearch(parse(""))).toBe("");
    expect(locationSearch(parse("lat=21.15&lon=79.07&name=Ajni"))).toBe("?lat=21.15000&lon=79.07000&name=Ajni");
  });
});
