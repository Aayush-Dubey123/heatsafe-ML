import { describe, expect, it } from "vitest";
import { exposureBin, fmtDistance, fmtNumber, fmtRank, fmtTemp, isExposureLevel } from "./format";

describe("format", () => {
  it("formats temperatures and missing values", () => {
    expect(fmtTemp(32.71)).toBe("32.7");
    expect(fmtTemp(null)).toBe("–");
    expect(fmtTemp(Number.NaN)).toBe("–");
  });

  it("formats distances in m or km", () => {
    expect(fmtDistance(0.441)).toBe("440 m");
    expect(fmtDistance(1.24)).toBe("1.2 km");
  });

  it("formats numbers per locale", () => {
    expect(fmtNumber(182408, "en")).toBe("182,408");
    expect(fmtNumber(null, "en")).toBe("–");
  });

  it("shows rank intervals only when they carry information", () => {
    expect(fmtRank(1, 1, 2)).toBe("1 [1–2]");
    expect(fmtRank(3, 3, 3)).toBe("3");
    expect(fmtRank(null, null, null)).toBe("–");
  });

  it("recognises exposure levels and bins indexes at the API cut-offs", () => {
    expect(isExposureLevel("very_high")).toBe(true);
    expect(isExposureLevel("bogus")).toBe(false);
    expect([0, 24.9, 25, 50, 75, 90, 100].map(exposureBin)).toEqual([0, 0, 1, 2, 3, 4, 4]);
  });
});
