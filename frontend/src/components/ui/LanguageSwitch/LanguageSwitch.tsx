import { useTranslation } from "react-i18next";
import { LANGUAGES, changeLanguage } from "../../../i18n/setup/i18n";
import type { LanguageCode } from "../../../i18n/setup/i18n";

/** Three-way language switch (English, Hindi, Marathi); each label is written in its own language. */
export function LanguageSwitch() {
  const { t, i18n } = useTranslation();
  const current = i18n.language;
  return (
    <div role="group" aria-label={t("lang.label")} style={{ display: "inline-flex", gap: 2 }}>
      {LANGUAGES.map((language) => (
        <button
          key={language.code}
          type="button"
          lang={language.code}
          className="btn"
          aria-pressed={current === language.code}
          onClick={() => void changeLanguage(language.code as LanguageCode)}
          style={{ minHeight: 40, padding: "0 10px", fontSize: "var(--fs-sm)" }}
        >
          {language.label}
        </button>
      ))}
    </div>
  );
}
