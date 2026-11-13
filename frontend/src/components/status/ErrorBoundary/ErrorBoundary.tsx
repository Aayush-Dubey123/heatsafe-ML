import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { withTranslation } from "react-i18next";
import type { WithTranslation } from "react-i18next";

interface Props extends WithTranslation {
  children: ReactNode;
}

interface State {
  failed: boolean;
}

/** Last line of defence: a rendering bug shows a calm message and a reload button instead of a blank page. */
class Boundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Unhandled UI error", error.message, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    const { t } = this.props;
    return (
      <div className="page">
        <div className="notice notice-danger stack" role="alert">
          <strong>{t("state.errorTitle")}</strong>
          <p>{t("state.generic")}</p>
          <button type="button" className="btn" onClick={() => window.location.reload()} style={{ alignSelf: "flex-start" }}>
            {t("state.retry")}
          </button>
        </div>
      </div>
    );
  }
}

export const ErrorBoundary = withTranslation()(Boundary);
