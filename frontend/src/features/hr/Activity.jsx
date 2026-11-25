import { Link } from "react-router-dom";
import { post } from "../../api/client";
import { useAct, useGet } from "../../api/hooks";
import { DataTable } from "../../components/DataTable";
import { useForm } from "../../components/FormModal";
import { Badge, Bars, Card, Grid, Kpi, Level, LineChart, Muted } from "../../components/ui";
import { d10, dt, num, pct, pretty, t } from "../../lib/i18n";

const KINDS = ["training", "course", "conference", "workshop", "supervision_hours"];

/** Spec §3.3: practitioner activity, sessions, referrals, quality, supervision participation, development, trends, unusual patterns (aggregates only). */
export default function Activity({ id, write }) {
  const { data: a } = useGet(`/hr/practitioners/${id}/activity`);
  const ask = useForm(), act = useAct();
  if (!a) return null;
  const s = a.sessions, q = a.quality, dev = a.professional_development, u = a.unusual_activity;
  const add = () => ask({
    title: t("Add development activity"), submit: t("Add"),
    fields: [{ name: "kind", label: t("Kind"), type: "select", options: KINDS.map((k) => [k, pretty(k)]) }, { name: "title", label: t("Title") }, { name: "provider", label: t("Provider") },
      { name: "hours", label: t("Hours"), type: "number", value: 8 }, { name: "completed_on", label: t("Completed on"), type: "date" }],
    onSubmit: (v) => act(() => post(`/hr/practitioners/${id}/development`, { ...v, provider: v.provider || "" }), t("Development activity added")),
  });
  return (
    <>
      <h2 style={{ margin: "22px 0 10px" }}>{t("Activity & performance")}</h2>
      <Grid cols={4}>
        <Kpi n={s.last_28d.completed} label={t("Completed sessions (28 d)")} />
        <Kpi n={s.last_28d.scheduled} label={t("Scheduled sessions")} />
        <Kpi n={s.last_28d.cancelled + s.last_28d.no_show} label={t("Cancelled / no-show")} />
        <Kpi n={pct(s.completion_rate)} label={t("Completion rate")} />
        <Kpi n={a.referrals.received_56d} label={t("Referrals received (56 d)")} />
        <Kpi n={a.referrals.made_56d} label={t("Referrals made (56 d)")} />
        <Kpi n={num(q.avg_performance)} label={t("Average performance (1–5)")} />
        <Kpi n={pct(a.supervision_participation.attendance)} label={t("Supervision attendance")} tone={a.supervision_participation.attendance !== null && a.supervision_participation.attendance < 0.7 ? "high" : ""} />
      </Grid>
      <Grid style={{ marginTop: 14 }}>
        <Card title={t("Weekly completed sessions")}>{s.weekly.length ? <Bars data={Object.fromEntries(s.weekly.map((w) => [w.week, w.completed]))} /> : <Muted>{t("No data.")}</Muted>}</Card>
        <Card title={t("Performance trend")}><LineChart points={q.performance_trend} field="avg_score" caption={t("Average review score (1–5) per week")} /></Card>
        <Card title={t("Quality indicators")}>
          <DataTable rows={[{ id: 1, k: t("Reviews decided"), v: q.reviews.decided }, { id: 2, k: t("Reviews pending"), v: q.reviews.pending }, { id: 3, k: t("Reviews overdue"), v: q.reviews.overdue },
            { id: 4, k: t("Open quality issues"), v: q.issues.open }, { id: 5, k: t("All quality issues"), v: q.issues.total }]} columns={[{ h: t("Indicator"), f: (r) => r.k }, { h: t("Value"), f: (r) => num(r.v) }]} />
        </Card>
        <Card title={t("Professional development")} action={write && <button onClick={add}>{t("+ Add")}</button>}>
          <Muted>{t("{0} activities · {1} hours in the last 12 months", num(dev.count_12m), num(dev.hours_12m))}</Muted>
          <DataTable rows={dev.items} columns={[{ h: t("Title"), f: (r) => r.title }, { h: t("Kind"), f: (r) => pretty(r.kind) }, { h: t("Hours"), f: (r) => num(r.hours) }, { h: t("Completed on"), f: (r) => d10(r.completed_on) }]} />
        </Card>
        <Card title={t("Unusual activity (alerts about this person)")}>
          <DataTable rows={u.alerts} empty={t("No alerts.")} columns={[{ h: t("Alert"), f: (r) => <Link to={`/monitoring/alerts/${r.id}`}>{r.title}</Link> }, { h: t("Risk"), f: (r) => <Level level={r.risk_level} /> },
            { h: t("Status"), f: (r) => <Badge>{pretty(r.status)}</Badge> }, { h: t("Detected"), f: (r) => dt(r.detected_at) }]} />
          <Muted>{u.note}</Muted>
        </Card>
      </Grid>
    </>
  );
}
