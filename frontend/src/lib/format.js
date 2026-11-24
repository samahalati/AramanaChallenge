export { d10, dt, pct, pretty } from "./i18n";
export const today = () => new Date().toISOString().slice(0, 10);
export const inDays = (n) => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10);
export const qs = (obj) => Object.entries(obj).filter(([, v]) => v !== "" && v != null).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join("&");
