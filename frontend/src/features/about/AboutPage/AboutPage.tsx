import { useTranslation } from "react-i18next";
import { useMetadata } from "../../../api/queries/queries";
import { Tabs } from "../../../components/ui/Tabs/Tabs";

/** What the numbers mean, where they come from, and what they cannot tell you: one short view per tab, no scrolling. */
export function AboutPage() {
  const { t } = useTranslation();
  const metadata = useMetadata();
  const list = (key: string) => t(key, { returnObjects: true }) as string[];
  const bullets = (items: string[]) => (
    <ul style={{ margin: 0, paddingLeft: 20, display: "flex", flexDirection: "column", gap: 8 }}>
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );

  return (
    <div className="page" style={{ maxWidth: 820 }}>
      <h1 style={{ fontSize: "var(--fs-xl)", flex: "none" }}>{t("about.title")}</h1>
      <Tabs
        label={t("about.title")}
        tabs={[
          {
            id: "what",
            label: t("about.tabWhat"),
            content: (
              <div className="card stack" style={{ gap: 8 }}>
                <h2 style={{ fontSize: "var(--fs-lg)" }}>{t("about.whatTitle")}</h2>
                <p>{t("about.what")}</p>
                {metadata.data && <p className="small muted">{metadata.data.resolution_note}</p>}
              </div>
            ),
          },
          {
            id: "limits",
            label: t("about.tabLimits"),
            content: (
              <div className="card stack" style={{ gap: 8 }}>
                <h2 style={{ fontSize: "var(--fs-lg)" }}>{t("about.limitsTitle")}</h2>
                {bullets(list("about.limits"))}
              </div>
            ),
          },
          {
            id: "accuracy",
            label: t("about.tabAccuracy"),
            content: (
              <div className="card stack" style={{ gap: 8 }}>
                <h2 style={{ fontSize: "var(--fs-lg)" }}>{t("about.accuracyTitle")}</h2>
                <p>{t("about.accuracy")}</p>
              </div>
            ),
          },
          {
            id: "credits",
            label: t("about.tabCredits"),
            content: (
              <div className="card stack" style={{ gap: 8 }}>
                <h2 style={{ fontSize: "var(--fs-lg)" }}>{t("about.creditsTitle")}</h2>
                {bullets(list("about.credits"))}
              </div>
            ),
          },
          {
            id: "official",
            label: t("about.tabOfficial"),
            content: (
              <section className="notice notice-warn stack" style={{ gap: 8 }}>
                <h2 style={{ fontSize: "var(--fs-lg)" }}>{t("about.officialTitle")}</h2>
                <p>{t("about.official")}</p>
              </section>
            ),
          },
        ]}
      />
    </div>
  );
}
