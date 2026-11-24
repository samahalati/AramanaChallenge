import { NavLink } from "react-router-dom";
import { num, pretty, t } from "../lib/i18n";

export const Card = ({ title, children, className = "", action }) => (
  <div className={`card ${className}`}>
    {(title || action) && <div className="row between">{title && <h2>{title}</h2>}{action}</div>}
    {children}
  </div>
);
export const Kpi = ({ n, label, tone }) => <div className="card kpi"><span className={`n ${tone ? `badge b-${tone}` : ""}`}>{typeof n === "number" ? num(n) : n ?? "–"}</span><span className="l">{label}</span></div>;
export const Grid = ({ cols = 2, children, style }) => <div className={`grid g${cols}`} style={style}>{children}</div>;
export const Muted = ({ children }) => <p className="muted small">{children}</p>;
export const Notice = ({ children, tone }) => <div className={`notice ${tone || ""}`}>{children}</div>;

const GOOD = ["active", "approved", "completed", "valid", "closed_substantiated", "closed_no_action", "false_positive"];
const BAD = ["suspended", "terminated", "expired", "revoked", "needs_changes", "escalated", "open"];
export const Badge = ({ tone = "muted", children }) => <span className={`badge b-${tone}`}>{children}</span>;
export const Level = ({ level }) => <Badge tone={level}>{pretty(level)}</Badge>;
export const Status = ({ status }) => <Badge tone={GOOD.includes(status) ? "ok" : BAD.includes(status) ? "high" : "muted"}>{pretty(status)}</Badge>;

export const Tabs = ({ items }) => (
  <div className="tabs">{items.map(([to, label], i) => <NavLink key={to} to={to} end={i === 0}>{label}</NavLink>)}</div>
);

export function Bars({ data, color }) {
  const max = Math.max(1, ...Object.values(data));
  return (
    <div>{Object.entries(data).map(([k, v]) => (
      <div className="row nowrap" key={k} style={{ margin: "4px 0" }}>
        <span style={{ width: 130, fontSize: 12 }}>{pretty(k)}</span>
        <div className="bar" style={{ flex: 1 }}><i style={{ width: `${(100 * v) / max}%`, background: color?.(k) }} /></div><b>{num(v)}</b>
      </div>))}
    </div>
  );
}

export function LineChart({ points, field, caption }) {
  if (!points.length) return <Muted>{t("No data.")}</Muted>;
  const W = 520, H = 130, pad = 22, vals = points.map((p) => p[field]), lo = Math.min(...vals, 1), hi = Math.max(...vals, 5);
  const x = (i) => pad + (i * (W - 2 * pad)) / Math.max(1, points.length - 1), y = (v) => H - pad - ((v - lo) / (hi - lo || 1)) * (H - 2 * pad);
  return (
    <div style={{ color: "var(--brand)" }}>
      <svg viewBox={`0 0 ${W} ${H}`} className="svgc">
        <polyline fill="none" stroke="currentColor" strokeWidth="2" points={points.map((p, i) => `${x(i)},${y(p[field])}`).join(" ")} />
        {points.map((p, i) => <circle key={i} cx={x(i)} cy={y(p[field])} r="3.5" fill="currentColor"><title>{`${p.week}: ${num(p[field])}`}</title></circle>)}
      </svg>
      <Muted>{caption}</Muted>
    </div>
  );
}
