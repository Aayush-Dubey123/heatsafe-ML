import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { readStoredTheme, useTheme } from "./useTheme";

afterEach(() => {
  delete document.documentElement.dataset["theme"];
});

describe("useTheme", () => {
  it("defaults to light", () => {
    expect(readStoredTheme()).toBe("light");
    expect(renderHook(() => useTheme()).result.current.theme).toBe("light");
  });

  it("toggles, updates <html> and remembers the choice", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current.toggle());
    expect(result.current.theme).toBe("dark");
    expect(document.documentElement.dataset["theme"]).toBe("dark");
    expect(readStoredTheme()).toBe("dark");
    act(() => result.current.toggle());
    expect(document.documentElement.dataset["theme"]).toBe("light");
    expect(readStoredTheme()).toBe("light");
  });
});
