import { fieldLabel, lang, t } from "../lib/i18n";

/** Thin fetch wrapper: bearer token from sessionStorage, uniform error messages, auto sign-out on 401. */
const KEY = "aramana_session";
export const session = {
  get: () => JSON.parse(sessionStorage.getItem(KEY) || "null"),
  set: (value) => sessionStorage.setItem(KEY, JSON.stringify(value)),
  clear: () => sessionStorage.removeItem(KEY),
};

const message = (data, status) => {
  const d = data?.detail ?? data;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.join("، ");
  if (d && typeof d === "object") return Object.entries(d).map(([k, v]) => `${k === "non_field_errors" || k === "detail" ? "" : `${fieldLabel(k)}: `}${[].concat(v).join("، ")}`).join("؛ ");
  return t("Request failed ({0})", status);
};

export async function api(path, { method = "GET", body } = {}) {
  const token = session.get()?.token;
  const res = await fetch(`/api${path}`, {
    method,
    headers: { "Content-Type": "application/json", "Accept-Language": lang, ...(token && { Authorization: `Bearer ${token}` }) },
    body: body && JSON.stringify(body),
  });
  const data = await res.json().catch(() => null);
  if (res.status === 401 && token) { session.clear(); location.assign("/login"); }
  if (!res.ok) throw new Error(message(data, res.status));
  return data;
}
export const get = (path) => api(path);
export const post = (path, body = {}) => api(path, { method: "POST", body });
export const patch = (path, body) => api(path, { method: "PATCH", body });
