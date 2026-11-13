import { useRef } from "react";
import type { PointerEvent, ReactNode } from "react";
import { useTranslation } from "react-i18next";
import styles from "./BottomSheet.module.css";

interface BottomSheetProps {
  expanded: boolean;
  onExpandedChange: (expanded: boolean) => void;
  /** Always visible part (the answer). */
  summary: ReactNode;
  /** Shown when expanded on phones; always shown in the side panel on desktop. */
  children: ReactNode;
  label: string;
}

const SWIPE_PX = 30;

/**
 * Bottom sheet on phones (tap the handle or swipe it), a floating side panel on desktop.
 * The handle is a real button, so it works with keyboard and screen readers.
 */
export function BottomSheet({ expanded, onExpandedChange, summary, children, label }: BottomSheetProps) {
  const { t } = useTranslation();
  const startY = useRef<number | null>(null);
  const swiped = useRef(false);

  const onPointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    startY.current = event.clientY;
    swiped.current = false;
  };
  const onPointerUp = (event: PointerEvent<HTMLButtonElement>) => {
    if (startY.current === null) return;
    const delta = event.clientY - startY.current;
    startY.current = null;
    if (Math.abs(delta) > SWIPE_PX) {
      swiped.current = true;
      onExpandedChange(delta < 0);
    }
  };

  return (
    <section className={styles.sheet} data-expanded={expanded} aria-label={label}>
      <button
        type="button"
        className={styles.handle}
        aria-expanded={expanded}
        aria-label={expanded ? t("map.collapse") : t("map.expand")}
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
        onClick={() => {
          if (swiped.current) {
            swiped.current = false;
            return;
          }
          onExpandedChange(!expanded);
        }}
      >
        <span className={styles.grip} />
      </button>
      <div className={styles.summary}>{summary}</div>
      <div className={styles.body}>{children}</div>
    </section>
  );
}
