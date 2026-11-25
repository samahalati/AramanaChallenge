/** Frontend localisation: Persian (default) / English. The language is chosen once per page load (toggle = reload), so plain functions are enough.
 *  t("English source text", ...args)  -> Persian via lib/fa.js ({0} placeholders); unknown keys fall back to the English text.
 *  pretty(token)                      -> server vocabulary (/api/meta/labels) for enums, roles, evidence keys; else "snake_case" -> "snake case".
 *  Dates are shown in the Jalali calendar with Persian digits. */
import FA from "./fa";

const KEY = "aramana_lang";
const read = () => { try { return localStorage.getItem(KEY); } catch { return null; } };
export const lang = read() === "en" ? "en" : "fa";
export const isFa = lang === "fa";
export const setLang = (value) => { try { localStorage.setItem(KEY, value); } catch { /* private mode */ } location.reload(); };

let terms = {};
export async function loadLabels() {
  document.documentElement.lang = lang;
  document.documentElement.dir = isFa ? "rtl" : "ltr";
  document.title = isFa ? "آرامانا – پلتفرم حاکمیت و نظارت" : "Aramana – Governance & Supervision Platform";
  if (!isFa) return;
  try { terms = (await (await fetch("/api/meta/labels", { headers: { "Accept-Language": lang } })).json()).terms ?? {}; } catch { /* UI still works with English tokens */ }
}

export const t = (key, ...args) => {
  const text = (isFa && FA[key]) || key;
  return args.length ? text.replace(/\{(\d+)\}/g, (_, i) => args[i] ?? "") : text;
};

const DIGITS = "۰۱۲۳۴۵۶۷۸۹";
export const num = (x) => {
  if (x == null) return "–";
  const text = String(x);
  if (!isFa) return text;
  const fa = text.replace(/\d/g, (d) => DIGITS[d]).replace(".", "٫");
  return text.startsWith("-") ? `\u2066${fa}\u2069` : fa;   // keep the minus sign on the left of a negative number inside RTL text
};
export const pretty = (s) => terms[s] ?? String(s ?? "").replaceAll("_", " ");
export const term = (s) => terms[s] ?? s;
export const fieldLabel = (k) => terms[`field:${k}`] ?? String(k).replaceAll("_", " ");
export const pct = (x) => (x == null ? "–" : isFa ? `${num(Math.round(x * 100))}٪` : `${Math.round(x * 100)}%`);

const JALALI = "fa-IR-u-ca-persian";
const dateFmt = new Intl.DateTimeFormat(JALALI, { year: "numeric", month: "2-digit", day: "2-digit", timeZone: "UTC" });
const timeFmt = new Intl.DateTimeFormat(JALALI, { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: "UTC" });
const parse = (s) => new Date(/^\d{4}-\d\d-\d\d$/.test(s) ? `${s}T00:00:00Z` : /[zZ]|[+-]\d\d:?\d\d$/.test(s) ? s : `${s}Z`);
export const d10 = (s) => (!s ? "–" : isFa ? dateFmt.format(parse(String(s))) : String(s).slice(0, 10));
export const dt = (s) => (!s ? "–" : isFa ? `${dateFmt.format(parse(String(s)))} ${timeFmt.format(parse(String(s)))}` : String(s).replace("T", " ").slice(0, 16));
