/* Browser smoke test: drives the real React UI as each role, in Persian (default) and English.
   Usage: BASE=http://localhost:5173 SHOTS=./shots/ LANGS=fa,en node e2e/smoke.cjs   (Playwright must be resolvable by Node.)
   Selectors are written with the English source strings and translated through the UI's own dictionary (src/lib/fa.js) and the API vocabulary. */
const { chromium } = require("playwright");
const BASE = process.env.BASE || "http://localhost:5173";
const SHOTS = process.env.SHOTS || "./shots/";
const LANGS = (process.env.LANGS || "fa,en").split(",");
const problems = [];
let L = "fa", FA = {}, TERMS = {};
const DIG = "۰۱۲۳۴۵۶۷۸۹";
const T = (key, ...args) => { const s = ((L === "fa" && FA[key]) || key).replace(/\{(\d+)\}/g, (_, i) => args[i] ?? ""); return L === "fa" ? s.replace(/\d/g, (d) => DIG[d]) : s; };
const term = (token) => (L === "fa" ? TERMS[token] ?? token : token.replaceAll("_", " "));
const QUESTIONS = { fa: ["چرا امتیاز این‌قدر بالاست؟", "آیا باید این متخصص را تعلیق کنیم؟"], en: ["Why is the score so high?", "Should we suspend this practitioner?"] };

async function as(browser, label, steps) {
  label = T(label);
  const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 } });
  await ctx.addInitScript((l) => localStorage.setItem("aramana_lang", l), L);
  const page = await ctx.newPage();
  page.on("console", (m) => m.type() === "error" && !m.text().includes("403") && problems.push(`[${L}:${label}] console: ${m.text()}`));
  page.on("pageerror", (e) => problems.push(`[${L}:${label}] pageerror: ${e.message}`));
  page.on("response", (r) => r.status() >= 500 && problems.push(`[${L}:${label}] ${r.status()} ${r.url()}`));
  await page.goto(BASE);
  await page.getByRole("button", { name: label, exact: true }).click();
  await page.waitForSelector("main");
  await steps(page);
  await page.context().close();
}
const shot = (page, name) => page.screenshot({ path: `${SHOTS}${L}-${name}.png`, fullPage: true });
const nav = async (page, text) => { await page.getByRole("link", { name: T(text), exact: true }).first().click(); await page.waitForTimeout(500); };

(async () => {
  FA = (await import("../src/lib/fa.js")).default;
  const browser = await chromium.launch();
  for (const lang of LANGS) {
    L = lang;
    TERMS = L === "fa" ? (await (await fetch(`${process.env.API || "http://localhost:8000"}/api/meta/labels`, { headers: { "Accept-Language": "fa" } })).json()).terms : {};
    const [why, suspend] = QUESTIONS[L];
    await as(browser, "Compliance reviewer", async (p) => {
      await p.waitForSelector(`text=${T("Alerts visible to you")}`);
      await shot(p, "01-monitoring-overview");
      await nav(p, "Alerts"); await p.waitForSelector("tbody tr");
      await shot(p, "02-alerts");
      await p.locator("tbody tr").first().click(); await p.waitForSelector(`text=${T("Why this score – traceable to indicators")}`);
      const start = p.getByRole("button", { name: term("start_review"), exact: true });
      if (await start.count()) { await start.click(); await p.waitForSelector(`text=${T("{0} – recorded", T("Start review"))}`); }   // tolerant: alert may already be under review
      await p.getByRole("button", { name: term("comment"), exact: true }).click(); await p.fill("textarea", "Reviewing the evidence now."); await p.getByRole("button", { name: T("Submit"), exact: true }).click();
      await p.waitForSelector("text=Reviewing the evidence now.");
      // --- guarded AI assistant: briefing, grounded answer, refusal, citations, draft note
      await p.getByRole("button", { name: T("Generate briefing") }).click(); await p.waitForSelector(`text=${T("guardrails {0}/{1} passed", 6, 6)}`);
      const ask = p.getByPlaceholder(T("Ask about this alert, e.g. “Why is the score so high?” or “What could be a benign explanation?”"));
      await ask.fill(why); await p.getByRole("button", { name: T("Ask"), exact: true }).click();
      await p.waitForSelector(`text=${T("Q:")} ${why}`);
      await ask.fill(suspend); await p.getByRole("button", { name: T("Ask"), exact: true }).click();
      await p.waitForSelector(`text=${T("refused by the assistant")}`, { timeout: 60000 });
      await p.locator("button.chip").first().click(); await p.waitForSelector(".source");
      await p.getByText(T("Use as draft note")).first().click(); await p.waitForSelector(`text=${T("Add comment (AI-assisted draft – edit before submitting)")}`);
      await p.getByRole("button", { name: T("Cancel") }).click();
      await shot(p, "03b-assistant");
      await shot(p, "03-alert-detail");
      await nav(p, "Scoring & evaluation"); await p.waitForSelector(`text=${T("Measured performance on the synthetic dataset")}`); await shot(p, "04-evaluation");
      await nav(p, "Audit"); await p.waitForSelector(`text=${T("chain verified ({0} entries)", "").split("(")[0].trim()}`); await shot(p, "05-audit");
    });
    await as(browser, "HR administrator", async (p) => {
      await p.waitForSelector(`text=${T("Credentials expiring ≤ 60 days or expired")}`); await shot(p, "06-hr-dashboard");
      await nav(p, "Practitioners"); await p.waitForSelector("tbody tr");
      await p.fill(`input[placeholder^="${T("Search name or e-mail…").slice(0, 8)}"]`, "therapist1@"); await p.waitForTimeout(600);
      await p.locator("tbody tr").first().click(); await p.waitForSelector(`text=${T("Credentials & licences")}`);
      await p.getByRole("button", { name: term("suspend"), exact: true }).click(); await p.waitForSelector(`text=${T("A human HR decision. It is audited and never triggered by an AI risk score.")}`); await shot(p, "07-hr-suspend-dialog");
      await p.getByRole("button", { name: T("Cancel") }).click();
      await nav(p, "Supervision assignments"); await p.waitForSelector(`text=${T("Current supervisor–supervisee relationships")}`); await shot(p, "08-assignments");
    });
    await as(browser, "Clinical supervisor", async (p) => {
      await p.waitForSelector(`text=${T("Assigned supervisees")}`); await shot(p, "09-supervision");
      await nav(p, "Reviews"); await p.waitForSelector("tbody tr");
      await p.locator("tbody a").first().click(); await p.waitForSelector(`text=${T("Supervision notes")}`); await shot(p, "10-review");
      await nav(p, "Quality issues"); await shot(p, "11-issues");
    });
    await as(browser, "Platform admin", async (p) => {
      await p.waitForSelector(`text=${T("Platform accounts")}`); await shot(p, "12-admin");
      await p.goto(BASE + "/hr"); await p.waitForSelector(`text=${T("Page not available for your role.")}`);
    });
    await as(browser, "Therapist", async (p) => { await p.waitForSelector(`text=${T("My sessions (latest 25)")}`); await shot(p, "13-therapist"); });
    await as(browser, "Assistant counselor", async (p) => { await p.waitForSelector(`text=${T("My referrals")}`); await p.getByRole("button", { name: T("+ New referral") }).click(); await p.waitForSelector(`text=${T("Need → eligible practitioner")}`); await shot(p, "14-counselor"); });
  }
  console.log(problems.length ? problems.join("\n") : `UI SMOKE TEST PASSED (${LANGS.join(", ")}): no console errors, no 5xx`);
  await browser.close();
})().catch((e) => { console.error("FAILED:", e.message.split("\n").slice(0, 4).join(" | ")); process.exit(1); });
