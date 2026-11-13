import { useCallback, useState } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "heatsafe.theme";

/** The saved choice; light is the default and is also used when storage is unavailable. */
export function readStoredTheme(): Theme {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

/** Put the theme on <html> so the CSS tokens switch. */
export function applyTheme(theme: Theme): void {
  document.documentElement.dataset["theme"] = theme;
}

/** Light/dark theme with a toggle that remembers the choice on this device. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => (document.documentElement.dataset["theme"] === "dark" ? "dark" : "light"));

  const toggle = useCallback(() => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    setTheme(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* the choice just will not be remembered */
    }
  }, [theme]);

  return { theme, toggle };
}
