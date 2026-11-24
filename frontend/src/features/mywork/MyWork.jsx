import { get, patch, post } from "../../api/client";
import { useAct, useGet } from "../../api/hooks";
import { useAuth } from "../../auth/AuthContext";
import { DataTable } from "../../components/DataTable";
import { useForm } from "../../components/FormModal";
import { Page, Query } from "../../components/Query";
import { Card, Grid, Status } from "../../components/ui";
import { d10, dt, num, pretty, t } from "../../lib/i18n";

const NEEDS = ["trauma", "anxiety", "depression", "couples", "child", "addiction"];

function Counselor() {
  const ask = useForm(), act = useAct();
  const refer = async () => {   // policy-valid choices: every (need -> eligible practitioner) pair
    const lists = await Promise.all(NEEDS.map((need) => get(`/referrals/eligible?need=${need}`).then((rows) => rows.map((p) => [`${need}|${p.id}`, `${pretty(need)} ← ${p.name}`]))));
    ask({ title: t("New referral"), submit: t("Refer"), intro: t("Choices follow the assignment policy (specialisation, capacity)."),
      fields: [{ name: "client_ref", label: t("Client reference (e.g. C-0001)") }, { name: "target", label: t("Need → eligible practitioner"), type: "select", options: lists.flat() }],
      onSubmit: ({ client_ref, target }) => { const [need, id] = target.split("|"); return act(() => post("/referrals", { client_ref, need, to_practitioner_id: +id }), t("Referral created")); } });
  };
  return (
    <Page title={t("My referrals")} sub={t("You see only your own referrals.")}>
      <Query path="/referrals/mine">{(rows) => (
        <Card title={t("Referrals")} action={<button className="primary" onClick={refer}>{t("+ New referral")}</button>}>
          <DataTable rows={rows.slice(0, 40)} columns={[{ h: t("Client"), f: (r) => <span dir="ltr">{r.client_ref}</span> }, { h: t("Need"), f: (r) => pretty(r.need) }, { h: t("To"), f: (r) => `#${num(r.to_practitioner_id)}` }, { h: t("When"), f: (r) => dt(r.created_at) }]} />
        </Card>
      )}</Query>
    </Page>
  );
}

function Therapist() {
  const { user } = useAuth();
  const { data: sessions } = useGet(`/clinical/practitioners/${user.id}/sessions`);
  const { data: clients = [] } = useGet("/clinical/my-clients");
  const { data: rv } = useGet("/supervision/my-reviews");
  const ask = useForm(), act = useAct();
  const schedule = () => ask({ title: t("Schedule a session"), submit: t("Schedule"), intro: t("Overlapping sessions are accepted but monitored."),
    fields: [{ name: "client_ref", label: t("Client"), type: "select", options: clients.map((c) => [c.client_ref, `${c.client_ref} (${pretty(c.primary_need)})`]) }, { name: "scheduled_start", label: t("Start"), type: "datetime-local" },
      { name: "duration_min", label: t("Duration (min)"), type: "number", value: 50 }, { name: "mode", label: t("Mode"), type: "select", options: [["online", pretty("online")], ["in_person", pretty("in_person")]] }, { name: "location_code", label: t("Location (in person)") }],
    onSubmit: (v) => act(() => post("/clinical/sessions", { ...v, scheduled_start: new Date(v.scheduled_start).toISOString() }), t("Session scheduled")) });
  return (
    <Page title={t("My work")} sub={t("Your sessions, supervision feedback and corrective actions.")}>
      <Grid>
        <Card title={t("My sessions (latest 25)")} action={<button className="primary" onClick={schedule}>{t("+ Schedule session")}</button>}>
          <DataTable rows={sessions?.slice(0, 25)} columns={[{ h: t("Start"), f: (s) => dt(s.scheduled_start) }, { h: t("Client"), f: (s) => <span dir="ltr">{s.client_ref}</span> }, { h: t("Mode"), f: (s) => pretty(s.mode) }, { h: t("Status"), f: (s) => <Status status={s.status} /> },
            { h: "", f: (s) => s.status === "scheduled" && <a onClick={() => act(() => patch(`/clinical/sessions/${s.id}`, { status: "cancelled" }), t("Cancelled"))}>{t("cancel")}</a> }]} />
        </Card>
        <Card title={t("Supervision feedback")}>
          <DataTable rows={rv?.reviews.slice(0, 10)} columns={[{ h: t("Case"), f: (r) => r.case_ref }, { h: t("Outcome"), f: (r) => <Status status={r.status} /> }, { h: t("Score"), f: (r) => num(r.performance_score) }, { h: t("Feedback"), f: (r) => r.feedback }]} />
          <h3>{t("Corrective actions")}</h3>
          <DataTable rows={rv?.corrective_actions} columns={[{ h: t("Action"), f: (a) => a.description }, { h: t("Due"), f: (a) => d10(a.due_date) }, { h: t("Status"), f: (a) => <Status status={a.status} /> },
            { h: "", f: (a) => a.status === "open" && <a onClick={() => act(() => patch(`/supervision/corrective-actions/${a.id}`, { status: "completed" }), t("Marked done"))}>{t("mark done")}</a> }]} />
        </Card>
      </Grid>
    </Page>
  );
}

export default function MyWork() {
  return useAuth().user.role === "assistant_counselor" ? <Counselor /> : <Therapist />;
}
