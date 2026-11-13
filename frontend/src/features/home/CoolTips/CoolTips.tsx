import { useTranslation } from "react-i18next";
import { Icon } from "../../../components/ui/Icon/Icon";

/** A few general, non-medical ways to stay cool, always next to a pointer to the official advisories. */
export function CoolTips({ bare = false }: { bare?: boolean }) {
  const { t } = useTranslation();
  const items = t("tips.items", { returnObjects: true }) as string[];
  return (
    <section className={bare ? "stack" : "card stack"} aria-labelledby="tips-title" style={bare ? { gap: 10, height: "100%", minHeight: 0 } : { gap: 10 }}>
      <h2 id="tips-title" style={{ fontSize: "var(--fs-lg)" }} className={bare ? "sr-only" : undefined}>{t("tips.title")}</h2>
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 10, ...(bare ? { flex: 1, minHeight: 0 } : {}) }}>
        {items.map((item) => (
          <li key={item} style={{ display: "flex", gap: 10, alignItems: "center", ...(bare ? { flex: 1, maxHeight: 96, background: "var(--surface-2)", borderRadius: "var(--radius-sm)", padding: "8px 12px" } : {}) }}>
            <span style={{ color: "var(--good)", marginTop: 2 }}><Icon name="drop" size={18} /></span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
      <p className="small muted">{t("tips.note")} {t("disclaimer.advisory")}</p>
    </section>
  );
}
