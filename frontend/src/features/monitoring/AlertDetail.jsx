import { Link, useParams } from "react-router-dom";
import { post } from "../../api/client";
import { useAct } from "../../api/hooks";
import { useAuth } from "../../auth/AuthContext";
import { DataTable } from "../../components/DataTable";
import { useForm } from "../../components/FormModal";
import { Query } from "../../components/Query";
import { Badge, Card, Grid, Level, Muted, Notice, Status } from "../../components/ui";
import { dt, isFa, num, pretty, t, term } from "../../lib/i18n";
import AssistantPanel from "./AssistantPanel";
import { LEVEL_COLOR } from "./Overview";

const LABELS = { start_review: "Start review", assign: "Assign", comment: "Add comment", request_info: "Request additional information", provide_info: "Record information received",
  escalate: "Escalate", false_positive: "Mark as false positive", close_no_action: "Close – no action", close_substantiated: "Close – substantiated", reopen: "Reopen" };
const NOTE_MIN = { request_info: 10, escalate: 10, false_positive: 10, close_no_action: 10, close_substantiated: 30, reopen: 10, comment: 3 };
const fmt = (v) => (v == null ? "–" : typeof v === "object" ? JSON.stringify(v) : typeof v === "boolean" ? (v ? t("yes") : t("no")) : /^\d{4}-\d\d-\d\dT/.test(v) ? dt(v) : term(String(v)));

function Evidence({ items }) {
  const groups = Object.groupBy(items, (e) => e.type || "item");
  return Object.entries(groups).map(([type, rows]) => {
    const keys = [...new Set(rows.flatMap((r) => Object.keys(r)).filter((k) => k !== "type"))];
    return <div key={type}><h3>{pretty(type)} ({num(rows.length)})</h3><div className="scroll"><DataTable rows={rows.slice(0, 40)} columns={keys.map((k) => ({ h: pretty(k), f: (r) => fmt(r[k]) }))} /></div></div>;
  });
}

function Breakdown({ rows }) {
  const max = Math.max(1, ...rows.map((b) => b.points));
  return (
    <DataTable rows={rows.map((b, i) => ({ ...b, id: i }))} columns={[{ h: t("Indicator"), f: (b) => <div>{b.label}<div className="small muted">{b.note}</div></div> }, { h: t("Method"), f: (b) => b.method_label ?? pretty(b.method) },
      { h: t("Value"), f: (b) => String(b.value) }, { h: t("Ref"), f: (b) => String(b.threshold) }, { h: t("Points"), f: (b) => <div><b>{num(b.points.toFixed(1))}</b><div className="bar"><i style={{ width: `${(100 * b.points) / max}%` }} /></div></div> }]} />
  );
}

export default function AlertDetail() {
  const { id } = useParams();
  const { can } = useAuth();
  const ask = useForm(), act = useAct();
  return (
    <Query path={`/alerts/${id}`}>{(a) => {
      const send = (action) => (v) => act(() => post(`/alerts/${id}/actions`, { action, note: v?.note, assign_to: v?.assign_to }), t("{0} – recorded", t(LABELS[action])));
      const doAction = (action) => action === "start_review" ? send(action)() : ask({
        title: t(LABELS[action]), submit: t("Submit"), onSubmit: send(action), intro: action === "close_substantiated" ? t("Substantiation is a recorded human finding. It does not trigger any automatic sanction.") : null,
        fields: [{ name: "note", label: NOTE_MIN[action] ? t("Documented note (min {0} chars)", num(NOTE_MIN[action])) : t("Note (optional)"), type: "textarea" }, ...(action === "assign" ? [{ name: "assign_to", label: t("Assignee user id (blank = me)"), type: "number" }] : [])],
      });
      const route = () => ask({ title: t("Route to the practitioner's supervisor"), submit: t("Route"), fields: [{ name: "note", label: t("Note for the supervisor (≥10 chars; no misconduct allegations)"), type: "textarea" }],
        onSubmit: (v) => act(() => post(`/alerts/${id}/route-to-supervisor`, v), (r) => t("Routed to supervisor #{0}", num(r.supervisor_id))) });
      const draft = (text) => ask({ title: t("Add comment (AI-assisted draft – edit before submitting)"), submit: t("Submit"), intro: t("You are responsible for this text. Verify every statement against the cited evidence."), onSubmit: send("comment"),
        fields: [{ name: "note", label: t("Documented note (min {0} chars)", num(NOTE_MIN.comment)), type: "textarea", value: text }] });
      const canRoute = can("alerts:investigate") && ["operational", "clinical"].includes(a.domain) && a.allowed_actions.length > 1;
      return (
        <>
          <p><Link to="/monitoring/alerts">{isFa ? "→" : "←"} {t("Alerts")}</Link></p>
          <Card>
            <div className="row between nowrap">
              <div>
                <div className="muted small"><span dir="ltr">{a.alert_uid}</span> · {t("category")} {a.category} ({a.category_label}) · {t("domain")} {pretty(a.domain)} · {t("routed to")} {a.routed_to.map(pretty).join("، ")}</div>
                <h2 style={{ margin: "4px 0" }}>{a.title}</h2>
                <div className="row"><Level level={a.risk_level} /><Status status={a.status} />{a.methods.map((m) => <Badge key={m}>{pretty(m)}</Badge>)}{a.related_users.map((u) => <span key={u.id} className="small muted">{pretty(u.role_in_alert)}: {u.name} ({pretty(u.role)})</span>)}</div>
              </div>
              <div style={{ textAlign: "end" }}><div className="score" style={{ color: LEVEL_COLOR[a.risk_level] }}>{num(Math.round(a.risk_score))}</div><div className="muted small">{t("risk score / 100")}</div></div>
            </div>
            <Notice tone="info">{a.advisory}</Notice>
          </Card>
          <Grid style={{ marginTop: 14 }}>
            <Card title={t("Investigation actions")}>
              <div className="row">
                {a.allowed_actions.map((x) => <button key={x} className={["close_substantiated", "escalate"].includes(x) ? "danger" : x === "start_review" ? "primary" : ""} onClick={() => doAction(x)}>{pretty(x)}</button>)}
                {canRoute && <button onClick={route}>{t("Route to supervisor")}</button>}
              </div>
              <h3>{t("Recommended investigation action")}</h3><p>{a.recommended_action}</p>
              <h3>{t("Longitudinal context")}</h3><Muted>{t("{0} other alerts for this subject.", num(a.longitudinal_context.other_alerts_for_subject))} {a.longitudinal_context.note}</Muted>
            </Card>
            <Card title={t("Why this score – traceable to indicators")}><Breakdown rows={a.score_breakdown} /><Muted>{t("Ruleset {0} · model {1}", a.ruleset_version, a.model_version)}</Muted></Card>
          </Grid>
          {can("alerts:investigate") && <div style={{ marginTop: 14 }}><AssistantPanel alertId={id} onDraft={draft} /></div>}
          <Card title={t("Explanation")} className="spaced"><pre className="expl">{a.explanation}</pre></Card>
          <Grid style={{ marginTop: 14 }}>
            <Card title={t("Supporting evidence")}><Evidence items={a.evidence} /></Card>
            <Card title={t("Investigation history")}>
              <div className="timeline">{a.timeline.map((e) => (
                <div className="ev" key={e.id}><div><b>{pretty(e.action)}</b>{e.to_status && ` ${isFa ? "←" : "→"} ${pretty(e.to_status)}`}</div><div className="small muted">{dt(e.ts)} · {e.actor}</div>{e.note && <div>{e.note}</div>}</div>))}
              </div>
            </Card>
          </Grid>
        </>
      );
    }}</Query>
  );
}
