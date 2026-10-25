/**
 * Small hand-drawn inline SVG icon set (24×24, stroke = currentColor).
 * Icons are always decorative: aria-hidden, so accessible names come from the text next to them.
 */
import type { ReactNode } from "react";

const PATHS: Record<string, ReactNode> = {
  play: <path d="M8 5.2v13.6a.8.8 0 0 0 1.2.7l11-6.8a.8.8 0 0 0 0-1.4l-11-6.8A.8.8 0 0 0 8 5.2z" fill="currentColor" />,
  pause: (
    <>
      <rect x="6" y="4.5" width="4" height="15" rx="1.2" fill="currentColor" stroke="none" />
      <rect x="14" y="4.5" width="4" height="15" rx="1.2" fill="currentColor" stroke="none" />
    </>
  ),
  stop: <rect x="5.5" y="5.5" width="13" height="13" rx="2" fill="currentColor" stroke="none" />,
  home: (
    <>
      <path d="M3.5 10.5 12 3.5l8.5 7V19a1.5 1.5 0 0 1-1.5 1.5h-4v-6h-6v6H5A1.5 1.5 0 0 1 3.5 19z" />
    </>
  ),
  map: (
    <>
      <path d="M9 4 3.5 6.2v13.6L9 17.6l6 2.4 5.5-2.2V4.2L15 6.4z" />
      <path d="M9 4v13.6M15 6.4V20" />
    </>
  ),
  history: (
    <>
      <path d="M3.5 12a8.5 8.5 0 1 0 2.5-6L3.5 8.5" />
      <path d="M3.5 3.5v5h5" />
      <path d="M12 7.5V12l3 2" />
    </>
  ),
  settings: (
    <>
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  sound: (
    <>
      <path d="M11 5 6.5 9H3.5v6h3L11 19z" fill="currentColor" />
      <path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9.2 9.2 0 0 1 0 13" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 12a8 8 0 1 1-2.35-5.65L20 8.5" />
      <path d="M20 3.5v5h-5" />
    </>
  ),
  rooms: (
    <>
      <rect x="3.5" y="3.5" width="7" height="7" rx="1.5" />
      <rect x="13.5" y="3.5" width="7" height="7" rx="1.5" />
      <rect x="3.5" y="13.5" width="7" height="7" rx="1.5" />
      <rect x="13.5" y="13.5" width="7" height="7" rx="1.5" />
    </>
  ),
  check: <path d="M5 12.5 9.5 17 19 7.5" />,
  alert: (
    <>
      <path d="M10.3 4.3 2.6 17.6A2 2 0 0 0 4.3 20.6h15.4a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0z" />
      <path d="M12 9.5v4.5" />
      <circle cx="12" cy="17.2" r="0.6" fill="currentColor" />
    </>
  ),
  robot: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3.6 10.5h16.8" />
      <circle cx="12" cy="6.9" r="1.5" fill="currentColor" stroke="none" />
      <circle cx="12" cy="15.5" r="2.2" />
    </>
  ),
  bolt: <path d="M13 2.5 5 13.5h6l-1 8 8-11h-6z" fill="currentColor" />,
  offline: (
    <>
      <path d="M2 8.8a15 15 0 0 1 4.6-2.8M10.6 5.1A15 15 0 0 1 22 8.8M5 12.6a10 10 0 0 1 4.9-2.5M17.5 11.3a10 10 0 0 1 1.5 1.3M8.5 16.1a5 5 0 0 1 7 0" />
      <circle cx="12" cy="19.6" r="0.6" fill="currentColor" />
      <path d="M3 3l18 18" />
    </>
  ),
};

export type IconName = keyof typeof PATHS;

export function Icon({ name, className = "" }: { name: string; className?: string }) {
  const body = PATHS[name];
  if (!body) return null;
  return (
    <svg
      className={`icon ${className}`}
      viewBox="0 0 24 24"
      width="24"
      height="24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {body}
    </svg>
  );
}
