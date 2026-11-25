import { isFa } from "../lib/i18n";

/** Brand mark (a leaf: growth and care) + the name. Colours come from the theme variables, so it works in light and dark. */
export function Mark({ size = 34 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <path d="M32 6c14 8 22 20 22 32 0 12-9 20-22 20S10 50 10 38C10 26 18 14 32 6z" style={{ fill: "var(--brand)" }} />
      <path d="M32 18v36M32 30c-6-2-10-6-11-10M32 38c6-2 10-6 11-10" fill="none" style={{ stroke: "var(--bg)" }} strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export default function Logo() {
  return <span className="logo"><Mark /><span>{isFa ? "آرامانا" : "Aramana"}</span></span>;
}
