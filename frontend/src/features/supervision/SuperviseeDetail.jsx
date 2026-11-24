import { Link, useParams } from "react-router-dom";
import { post } from "../../api/client";
import { useAct } from "../../api/hooks";
import { DataTable } from "../../components/DataTable";
import { useForm } from "../../components/FormModal";
import { Query } from "../../components/Query";
import { Card, Grid, Status } from "../../components/ui";
import { inDays } from "../../lib/format";
import { d10, dt, isFa, num, pretty, t } from "../../lib/i18n";

export default function SuperviseeDetail() {
  const { id } = useParams();
  const ask = useForm(), act = useAct();
  const meeting = () => ask({ title: t("Schedule supervision meeting"), submit: t("Schedule"), fields: [{ name: "scheduled_at", label: t("When"), type: "datetime-local" }],
    onSubmit: (v) => act(() => post("/supervision/meetings", { supervisee_id: +id, scheduled_at: new Date(v.scheduled_at).toISOString() }), t("Meeting scheduled")) });
  const review = () => ask({ title: t("Open a review"), submit: t("Open"), fields: [{ name: "due_date", label: t("Due"), type: "date", value: inDays(7) }],
    onSubmit: (v) => act(() => post("/supervision/reviews", { supervisee_id: +id, due_date: v.due_date }), t("Review opened")) });
  return (
    <Query path={`/supervision/supervisees/${id}`}>{(d) => (
      <>
        <p><Link to="/supervision/supervisees">{isFa ? "→" : "←"} {t("Supervisees")}</Link></p>
        <Card>
          <div className="row between"><h2>{d.user.name} <Status status={d.user.status} /></h2><div className="row"><button onClick={meeting}>{t("Schedule meeting")}</button><button className="primary" onClick={review}>{t("+ Open review")}</button></div></div>
          <p className="muted">{t("Sessions last 28 days")}: {Object.entries(d.sessions_last_28d).map(([k, v]) => `${pretty(k)} ${num(v)}`).join(" · ") || "–"}</p>
        </Card>
        <Grid style={{ marginTop: 14 }}>
          <Card title={t("Reviews")}><DataTable rows={d.reviews} columns={[{ h: t("Case"), f: (r) => <Link to={`/supervision/reviews/${r.id}`}>{r.case_ref}</Link> }, { h: t("Status"), f: (r) => <Status status={r.status} /> }, { h: t("Due"), f: (r) => d10(r.due_date) }, { h: t("Doc"), f: (r) => (r.has_documentation ? "✓" : "–") }]} /></Card>
          <Card title={t("Meetings")}>
            <DataTable rows={d.meetings} columns={[{ h: t("When"), f: (r) => dt(r.scheduled_at) }, { h: t("Status"), f: (r) => <Status status={r.status} /> }]} />
            <h3>{t("Quality issues")}</h3>
            <DataTable rows={d.quality_issues} columns={[{ h: t("Title"), f: (r) => r.title }, { h: t("Cat."), f: (r) => pretty(r.category) }, { h: t("Sev."), f: (r) => pretty(r.severity) }, { h: t("Status"), f: (r) => <Status status={r.status} /> }]} />
          </Card>
        </Grid>
      </>
    )}</Query>
  );
}
