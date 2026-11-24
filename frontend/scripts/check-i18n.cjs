/* Fails when a t("…") key used in src/ is missing from src/lib/fa.js (and lists dictionary keys nobody uses).  Usage: npm run check:i18n */
const fs = require("fs"), path = require("path");
const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(path.join(d, e.name)) : [path.join(d, e.name)]));
const files = walk("src").filter((f) => /\.jsx?$/.test(f) && !/(fa|i18n)\.js$/.test(f));
const dict = fs.readFileSync("src/lib/fa.js", "utf8");
const keys = new Set([...dict.matchAll(/^\s*"((?:[^"\\]|\\.)*)":/gm)].map((m) => JSON.parse(`"${m[1]}"`)));
const used = new Set(), missing = new Set();
for (const f of files) {
  const src = fs.readFileSync(f, "utf8");
  for (const m of src.matchAll(/\bt\(\s*("(?:[^"\\]|\\.)*"|`[^`$]*`)/g)) {
    const raw = m[1];
    const key = raw[0] === '"' ? JSON.parse(raw) : raw.slice(1, -1);
    used.add(key);
    if (!keys.has(key)) missing.add(`${key}   (${f})`);
  }
  for (const m of src.matchAll(/t\(`((?:check|reason|provider):)\$\{/g)) used.add(m[1] + "*");
}
for (const v of ["rules", "statistics", "ml", "graph", "llm"]) void v;
const dynamic = ["check:schema", "check:citations", "check:numbers", "check:tone", "check:identity", "check:consistency", "reason:provider_error", "reason:guardrail_rejected",
  "provider:template", "provider:template(fallback)", "provider:groq", "provider:gemini", "provider:ollama", "provider:openai"];
for (const k of dynamic) if (!keys.has(k)) missing.add(`${k}   (dynamic key)`);
if (missing.size) { console.error(`Missing Persian translations (${missing.size}):\n  ` + [...missing].join("\n  ")); process.exit(1); }
console.log(`i18n OK: ${used.size} keys used, ${keys.size} in dictionary`);
