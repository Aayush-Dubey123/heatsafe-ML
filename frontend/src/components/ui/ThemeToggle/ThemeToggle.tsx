import { useTranslation } from "react-i18next";
import { useTheme } from "../../../hooks/useTheme/useTheme";
import { Icon } from "../Icon/Icon";

/** Round button that switches between the light and dark theme. */
export function ThemeToggle() {
  const { t } = useTranslation();
  const { theme, toggle } = useTheme();
  return (
    <button
      type="button"
      className="btn btn-icon"
      onClick={toggle}
      aria-label={theme === "dark" ? t("theme.toLight") : t("theme.toDark")}
      title={theme === "dark" ? t("theme.toLight") : t("theme.toDark")}
      style={{ minHeight: 40, width: 40 }}
    >
      <Icon name={theme === "dark" ? "sun" : "moon"} size={20} />
    </button>
  );
}
