import { useEffect, useState } from "react";

/**
 * How many rows of a given height fit in an element, kept up to date as it resizes.
 * Lets paged lists fill the screen exactly instead of leaving blank space or scrolling.
 * Attach `ref` to the container (it is a callback ref so late-mounted containers work).
 */
export function useFitRows(rowPx: number, reservedPx: number, fallback = 8) {
  const [element, ref] = useState<HTMLElement | null>(null);
  const [rows, setRows] = useState(fallback);

  useEffect(() => {
    if (!element || typeof ResizeObserver === "undefined") return;
    const update = () => setRows(Math.max(4, Math.floor((element.clientHeight - reservedPx) / rowPx)));
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, [element, rowPx, reservedPx]);

  return { ref, rows };
}
