import { useTranslation } from "react-i18next";
import { useMetadata } from "../../../api/queries/queries";

/** What the numbers mean, where they come from, and what they cannot tell you. Written for non-specialists. */
export function AboutPage() {
  const { t } = useTranslation();
  const metadata = useMetadata();
  const list = (key: string) => t(key, { returnObjects: true }) as string[];

  return (
    <div className="page stack" style={{ maxWidth: 760 }}>
      <h1 style={{ fontSize: "var(--fs-xl)" }}>{t("about.title")}</h1>

      <section className="stack" style={{ gap: 6 }}>
        <h2 style={{ fontSize: "var(--fs-lg)" }}>{t("about.whatTitle")}</h2>
        <p>{t("about.what")}</p>
        {metadata.data && (
          <p className="small muted">
            {metadata.data.resolution_note}
          </p>
        )}
      </section>

      <section className="stack" style={{ gap: 6 }}>
        <h2 style={{ fontSize: "var(--fs-lg)" }}>{t("about.limitsTitle")}</h2>
        <ul style={{ margin: 0, paddingLeft: 20, display: "flex", flexDirection: "column", gap: 6 }}>
          {list("about.limits").map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>

      <section className="stack" style={{ gap: 6 }}>
        <h2 style={{ fontSize: "var(--fs-lg)" }}>{t("about.accuracyTitle")}</h2>
        <p>{t("about.accuracy")}</p>
      </section>

      <section className="stack" style={{ gap: 6 }}>
        <h2 style={{ fontSize: "var(--fs-lg)" }}>{t("about.creditsTitle")}</h2>
        <ul style={{ margin: 0, paddingLeft: 20, display: "flex", flexDirection: "column", gap: 6 }}>
          {list("about.credits").map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>

      <section className="notice notice-warn stack" style={{ gap: 6 }}>
        <h2 style={{ fontSize: "var(--fs-lg)" }}>{t("about.officialTitle")}</h2>
        <p>{t("about.official")}</p>
      </section>
    </div>
  );
}
