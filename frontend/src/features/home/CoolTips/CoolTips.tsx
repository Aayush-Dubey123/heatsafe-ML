import { useTranslation } from "react-i18next";
import { Icon } from "../../../components/ui/Icon/Icon";

/** A few general, non-medical ways to stay cool, always next to a pointer to the official advisories. */
export function CoolTips() {
  const { t } = useTranslation();
  const items = t("tips.items", { returnObjects: true }) as string[];
  return (
    <section className="card stack" aria-labelledby="tips-title" style={{ gap: 10 }}>
      <h2 id="tips-title" style={{ fontSize: "var(--fs-lg)" }}>{t("tips.title")}</h2>
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 10 }}>
        {items.map((item) => (
          <li key={item} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
            <span style={{ color: "var(--good)", marginTop: 2 }}><Icon name="drop" size={18} /></span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
      <p className="small muted">{t("tips.note")} {t("disclaimer.advisory")}</p>
    </section>
  );
}
