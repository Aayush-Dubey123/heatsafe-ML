import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "../locales/en.json";
import hi from "../locales/hi.json";
import mr from "../locales/mr.json";

export const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिन्दी" },
  { code: "mr", label: "मराठी" },
] as const;

export type LanguageCode = (typeof LANGUAGES)[number]["code"];
const STORAGE_KEY = "heatsafe.lang";

function asLanguage(value: string | null | undefined): LanguageCode | undefined {
  const code = value?.toLowerCase().split("-")[0];
  return LANGUAGES.find((l) => l.code === code)?.code;
}

/** Pick the starting language: `?lang=` link, then the saved choice, then the browser, then English. */
export function detectLanguage(urlLang: string | null, stored: string | null, browser: string): LanguageCode {
  return asLanguage(urlLang) ?? asLanguage(stored) ?? asLanguage(browser) ?? "en";
}

export function readStoredLanguage(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

/** Initialise i18next once; safe to call again in tests (it just switches language). */
export async function initI18n(language: LanguageCode): Promise<void> {
  if (i18n.isInitialized) {
    await i18n.changeLanguage(language);
    return;
  }
  await i18n.use(initReactI18next).init({
    resources: { en: { translation: en }, hi: { translation: hi }, mr: { translation: mr } },
    lng: language,
    fallbackLng: "en",
    interpolation: { escapeValue: false },
    returnObjects: false,
  });
  document.documentElement.lang = language;
}

/** Switch language, remember it, and tell the browser (screen readers pick the right voice). */
export async function changeLanguage(language: LanguageCode): Promise<void> {
  await i18n.changeLanguage(language);
  document.documentElement.lang = language;
  try {
    window.localStorage.setItem(STORAGE_KEY, language);
  } catch {
    /* remembering the choice is optional */
  }
}

export default i18n;
