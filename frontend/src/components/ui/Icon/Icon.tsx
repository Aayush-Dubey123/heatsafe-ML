const PATHS = {
  pin: "M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21zM12 12a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z",
  locate: "M12 3v3M12 18v3M3 12h3M18 12h3M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4",
  drop: "M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z",
  hospital: "M5 4h14v16H5zM12 8v8M8 12h8",
  tree: "M12 3l5 7h-3l4 6H6l4-6H7l5-7zM12 16v5",
  shelter: "M3 11l9-7 9 7M5 10v10h14V10M10 20v-5h4v5",
  alert: "M12 4l9 16H3L12 4zM12 10v4M12 17h.01",
  offline: "M3 3l18 18M8.5 16.4a5 5 0 0 1 7 0M5 12.9a10 10 0 0 1 4-2.3M19 12.9a10 10 0 0 0-5.3-2.8M12 20h.01",
  external: "M14 4h6v6M20 4l-9 9M18 14v5H5V6h5",
  map: "M9 4L3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14",
  list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 11v5M12 8h.01",
  home: "M4 11l8-7 8 7v9H4z",
} as const;

export type IconName = keyof typeof PATHS;

interface IconProps {
  name: IconName;
  size?: number;
  /** Accessible name; omit for purely decorative icons next to a text label. */
  label?: string;
}

/** Small stroke icons (24x24 grid) drawn inline so the app needs no icon font or network request. */
export function Icon({ name, size = 18, label }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
