import { useState } from "react";
import { post } from "../../api/client";
import { useAct, useGet } from "../../api/hooks";
import { Badge, Card, Muted } from "../../components/ui";
import { dt, num, pretty, t } from "../../lib/i18n";

const PROVIDER_TONE = (p) => (p === "template" ? "muted" : p.includes("fallback") ? "medium" : "ok");

/** Clickable source chips: the reviewer can always see the exact evidence line behind a claim. */
function Cites({ ids, sources }) {
  const [open, setOpen] = useState(null);
  if (!ids.length) return null;
  return (
    <div style={{ marginTop: 4 }}>
      <span className="muted small">{t("Sources:")} </span>
      {ids.map((id) => <button key={id} type="button" className={`chip ${open === id ? "on" : ""}`} onClick={() => setOpen(open === id ? null : id)}>{id}</button>)}
      {open && <div className="small source">{open}: {sources[open]}</div>}
    </div>
  );
}

function GuardrailReport({ g }) {
  const [show, setShow] = useState(false);
  const checks = Object.entries(g.output.checks), passed = checks.filter(([, v]) => v === "pass").length;
  return (
    <div className="small" style={{ marginTop: 8 }}>
      <Badge tone={g.input.refused_reason ? "high" : passed === checks.length ? "ok" : "critical"}>
        {g.input.refused_reason ? t("refused by the assistant") : t("guardrails {0}/{1} passed", num(passed), num(checks.length))}
      </Badge>{" "}
      {g.output.fallback_used && <Badge tone="medium">{t("model reply rejected → deterministic fallback")}</Badge>}{" "}
      {g.output.attempts > 1 && !g.output.fallback_used && <Badge tone="medium">{t("repaired on retry")}</Badge>}{" "}
      <a onClick={() => setShow(!show)}>{show ? t("hide details") : t("details")}</a>
      {show && (
        <div className="source">
          <div>{t("Input: pseudonymised · {0} e-mail fragment(s) redacted · {1} evidence row(s) omitted", num(g.input.redacted), num(g.input.evidence_rows_omitted))}</div>
          <div>{t("Output checks")}: {checks.map(([k, v]) => `${v === "pass" ? "✔" : "✘"} ${t(`check:${k}`)}`).join("  ")}</div>
          <div>{t("Model attempts")}: {num(g.output.attempts)}{g.output.fallback_reason && ` · ${t("fallback reason")}: ${t(`reason:${g.output.fallback_reason}`)}`}</div>
          {g.output.rejected_violations.length > 0 && <div>{t("Rejected reply")}: <span dir="ltr">{g.output.rejected_violations.join(" | ")}</span></div>}
        </div>
      )}
    </div>
  );
}

const draftText = (ex) => {
  const c = ex.content;
  const body = ex.kind === "briefing"
    ? [c.summary, ...c.findings.map((f) => `- ${f.text} [${f.cites.join(", ")}]`), `${t("Benign explanations to rule out")}: ` + c.benign_explanations.join("؛ "), `${t("Verification steps")}: ` + c.verification_steps.join("؛ ")].join("\n")
    : `${t("Q:")} ${ex.question}\n${t("A:")} ${c.answer}`;
  return `${t("[AI-assisted draft – verified against the cited evidence by me]")}\n${body}`;
};

function Exchange({ ex, onDraft }) {
  const c = ex.content;
  return (
    <div className="exchange">
      <div className="row between">
        <span><b>{ex.kind === "briefing" ? t("Briefing") : t("Question")}</b> <Badge tone={PROVIDER_TONE(ex.provider)}>{t(`provider:${ex.provider}`)}</Badge> <span className="small muted">{dt(ex.created_at)}</span></span>
        {!ex.refused && <a onClick={() => onDraft(draftText(ex))}>{t("Use as draft note")}</a>}
      </div>
      {ex.kind === "answer" && <p><b>{t("Q:")}</b> {ex.question}</p>}
      {ex.kind === "briefing" ? (
        <>
          <p>{c.summary}</p>
          <ul>{c.findings.map((f, i) => <li key={i}>{f.text}<Cites ids={f.cites} sources={ex.citations} /></li>)}</ul>
          <b className="small">{t("Benign explanations to rule out")}</b><ul>{c.benign_explanations.map((x, i) => <li key={i}>{x}</li>)}</ul>
          <b className="small">{t("Verification steps")}</b><ul>{c.verification_steps.map((x, i) => <li key={i}>{x}</li>)}</ul>
        </>
      ) : (
        <>
          <p>{c.answer}</p>
          {c.insufficient_evidence && !ex.refused && <Muted>{t("The evidence does not support an answer.")}</Muted>}
          <Cites ids={c.cites} sources={ex.citations} />
        </>
      )}
      <GuardrailReport g={ex.guardrails} />
    </div>
  );
}

export default function AssistantPanel({ alertId, onDraft }) {
  const { data: history = [] } = useGet(`/alerts/${alertId}/assistant`);
  const [question, setQuestion] = useState("");
  const act = useAct();
  const brief = () => act(() => post(`/alerts/${alertId}/ai-summary`), (r) => t("Briefing ready ({0})", t(`provider:${r.provider}`)));
  const ask = async (e) => { e.preventDefault(); if (await act(() => post(`/alerts/${alertId}/assistant`, { question }), (r) => (r.refused ? t("Question refused by guardrail") : t("Answer ready")))) setQuestion(""); };
  return (
    <Card title={t("AI investigation assistant (advisory · evidence-bound · guardrailed)")} action={<button onClick={brief}>{t("Generate briefing")}</button>}>
      <Muted>{t("Works only from this alert's pseudonymised evidence, cites its sources, never recommends sanctions or names people, and every reply is validated before you see it. It cannot change anything.")}</Muted>
      <form className="row nowrap" onSubmit={ask}>
        <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder={t("Ask about this alert, e.g. “Why is the score so high?” or “What could be a benign explanation?”")} maxLength={300} />
        <button className="primary" type="submit" disabled={question.trim().length < 3}>{t("Ask")}</button>
      </form>
      {history.length === 0 ? <Muted>{t("No assistant activity yet for this alert.")}</Muted> : history.map((ex) => <Exchange key={ex.id} ex={ex} onDraft={onDraft} />)}
    </Card>
  );
}
