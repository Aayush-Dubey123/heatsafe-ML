import { useId, useState } from "react";
import type { KeyboardEvent, ReactNode } from "react";
import styles from "./Tabs.module.css";

export interface TabItem {
  id: string;
  label: string;
  content: ReactNode;
}

interface TabsProps {
  tabs: TabItem[];
  label: string;
  /** Controlled selection; leave out to let the tabs manage themselves. */
  value?: string;
  onChange?: (id: string) => void;
}

/**
 * Switch between views instead of scrolling a long page: each panel is sized to fit the space it is given.
 * Follows the WAI-ARIA tabs pattern (arrow keys, Home and End move between tabs).
 */
export function Tabs({ tabs, label, value, onChange }: TabsProps) {
  const base = useId();
  const [inner, setInner] = useState(tabs[0]?.id ?? "");
  const wanted = value ?? inner;
  const active = tabs.find((tab) => tab.id === wanted) ?? tabs[0];

  const select = (id: string) => {
    setInner(id);
    onChange?.(id);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const index = tabs.findIndex((tab) => tab.id === active?.id);
    const moves: Record<string, number> = {
      ArrowRight: (index + 1) % tabs.length,
      ArrowLeft: (index - 1 + tabs.length) % tabs.length,
      Home: 0,
      End: tabs.length - 1,
    };
    const next = moves[event.key];
    if (next === undefined) return;
    event.preventDefault();
    const target = tabs[next];
    if (target) {
      select(target.id);
      document.getElementById(`${base}-tab-${target.id}`)?.focus();
    }
  };

  if (!active) return null;
  return (
    <div className={styles.root}>
      <div role="tablist" aria-label={label} className={styles.list} onKeyDown={onKeyDown}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            id={`${base}-tab-${tab.id}`}
            type="button"
            role="tab"
            aria-selected={tab.id === active.id}
            aria-controls={`${base}-panel`}
            tabIndex={tab.id === active.id ? 0 : -1}
            className={styles.tab}
            onClick={() => select(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`${base}-panel`} aria-labelledby={`${base}-tab-${active.id}`} className={styles.panel}>
        {active.content}
      </div>
    </div>
  );
}
