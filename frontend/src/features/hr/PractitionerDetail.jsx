import { Link, useParams } from "react-router-dom";
import { get, patch, post } from "../../api/client";
import { useAct } from "../../api/hooks";
import { useAuth } from "../../auth/AuthContext";
import { DataTable } from "../../components/DataTable";
import { useForm } from "../../components/FormModal";
import { Query } from "../../components/Query";
import { Badge, Card, Grid, Muted, Status } from "../../components/ui";
import Activity from "./Activity";
import { SPECS } from "./Practitioners";
import { d10, isFa, num, pretty, t } from "../../lib/i18n";

// which lifecycle actions are offered from each status (the server's state machine is the authority)
const ACTIONS = { pending_onboarding: [["activate", "primary"], ["terminate", "danger"]], active: [["suspend"], ["terminate", "danger"]],
  suspended: [["reactivate", "primary"], ["terminate", "danger"]], terminated: [] };

export default function PractitionerDetail() {
  const { id } = useParams();
  const { can } = useAuth();
  const ask = useForm(), act = useAct(), write = can("hr:write");
  return (
    <Query path={`/hr/practitioners/${id}`}>{(d) => {
      const u = d.user;
      const lifecycle = (action) => ask({
        title: `${pretty(action)}: ${u.full_name}`, submit: pretty(action), intro: t("A human HR decision. It is audited and never triggered by an AI risk score."),
        fields: [{ name: "reason", label: t("Documented reason (required)"), type: "textarea" }],
        onSubmit: (v) => act(() => post(`/hr/practitioners/${id}/lifecycle`, { action, reason: v.reason }), t("{0} recorded", pretty(action))),
      });
      const editProfile = async () => {
        const units = await get("/hr/org-units");
        ask({
          title: t("Edit profile"), submit: t("Save"),
          fields: [{ name: "specialization", label: t("Specialisation"), type: "select", value: d.profile.specialization ?? "", options: [["", "–"], ...SPECS.map((s) => [s, pretty(s)])] },
            { name: "org_unit_id", label: t("Organisation unit"), type: "select", value: d.profile.org_unit_id ?? "", options: [["", "–"], ...units.map((x) => [x.id, x.name])] },
            { name: "employment_type", label: t("Employment"), type: "select", value: d.profile.employment_type, options: ["employee", "contractor", "volunteer"].map((x) => [x, pretty(x)]) },
            { name: "capacity_weekly_sessions", label: t("Weekly capacity"), type: "number", value: d.profile.capacity_weekly_sessions }, { name: "bio", label: t("Biography"), type: "textarea", value: d.profile.bio ?? "" }],
          onSubmit: (v) => act(() => patch(`/hr/practitioners/${id}/profile`, { specialization: v.specialization || null, org_unit_id: v.org_unit_id ? +v.org_unit_id : null,
            employment_type: v.employment_type, capacity_weekly_sessions: v.capacity_weekly_sessions ?? 0, bio: v.bio }), t("Profile updated")),
        });
      };
      const addCredential = () => ask({
        title: t("Add credential"), submit: t("Add"),
        fields: [{ name: "kind", label: t("Kind"), type: "select", options: ["license", "certification", "degree"].map((x) => [x, pretty(x)]) }, { name: "title", label: t("Title") }, { name: "number", label: t("Number") }, { name: "expires_on", label: t("Expires"), type: "date" }],
        onSubmit: (v) => act(() => post(`/hr/practitioners/${id}/credentials`, v), t("Credential added")),
      });
      const editCredential = (c) => ask({
        title: t("Update credential"), submit: t("Save"),
        fields: [{ name: "expires_on", label: t("New expiry"), type: "date", value: d10(c.expires_on) }, { name: "status", label: t("Status"), type: "select", value: c.status, options: ["valid", "expired", "revoked", "pending"].map((x) => [x, pretty(x)]) }],
        onSubmit: (v) => act(() => patch(`/hr/credentials/${c.id}`, v), t("Credential updated")),
      });
      const addContract = () => ask({
        title: t("Add contract"), submit: t("Add"),
        fields: [{ name: "kind", label: t("Type"), type: "select", options: ["permanent", "fixed_term", "contractor", "volunteer"].map((x) => [x, pretty(x)]) }, { name: "start_date", label: t("Start"), type: "date" }, { name: "end_date", label: t("End (optional)"), type: "date" }],
        onSubmit: (v) => act(() => post(`/hr/practitioners/${id}/contracts`, v), t("Contract added")),
      });
      const add = (fn) => write && <button onClick={fn}>{t("+ Add")}</button>;
      return (
        <>
          <p><Link to="/hr/practitioners">{isFa ? "→" : "←"} {t("Practitioners")}</Link></p>
          <Card>
            <div className="row between">
              <div>
                <h2>{u.full_name} <Status status={u.status} /></h2>
                <div className="muted"><span dir="ltr">{u.email}</span> · {pretty(u.role)} · {d.profile.specialization ? pretty(d.profile.specialization) : t("no specialisation")} · {d.profile.org_unit || t("no unit")} · {pretty(d.profile.employment_type)} · {t("capacity {0}/wk", num(d.profile.capacity_weekly_sessions))}</div>
              </div>
              {write && <div className="row"><button onClick={editProfile}>{t("Edit profile")}</button>{ACTIONS[u.status].map(([a, cls]) => <button key={a} className={cls} onClick={() => lifecycle(a)}>{pretty(a)}</button>)}</div>}
            </div>
          </Card>
          <Grid style={{ marginTop: 14 }}>
            <Card title={t("Credentials & licences")} action={add(addCredential)}>
              <DataTable rows={d.credentials} columns={[{ h: t("Title"), f: (r) => r.title }, { h: t("No."), f: (r) => r.number }, { h: t("Expires"), f: (r) => d10(r.expires_on) }, { h: t("Status"), f: (r) => <Status status={r.status} /> },
                { h: "", f: (r) => write && <a onClick={() => editCredential(r)}>{t("edit")}</a> }]} />
            </Card>
            <Card title={t("Contracts & agreements")} action={add(addContract)}>
              <DataTable rows={d.contracts} columns={[{ h: t("Type"), f: (r) => pretty(r.kind) }, { h: t("Start"), f: (r) => d10(r.start_date) }, { h: t("End"), f: (r) => d10(r.end_date) }, { h: t("Status"), f: (r) => <Status status={r.status} /> }]} />
            </Card>
            <Card title={t("Supervision relationships (effective-dated history)")}>
              <DataTable rows={d.assignments} columns={[{ h: t("Supervisor"), f: (r) => r.supervisor }, { h: t("Supervisee"), f: (r) => r.supervisee }, { h: t("From"), f: (r) => d10(r.effective_from) },
                { h: t("To"), f: (r) => (r.current ? <Badge tone="ok">{t("current")}</Badge> : d10(r.effective_to)) }]} />
            </Card>
            <Card title={t("Complete activity & status history")}>
              <DataTable rows={d.lifecycle} columns={[{ h: t("Date"), f: (r) => d10(r.effective_date) }, { h: t("Event"), f: (r) => pretty(r.event) }, { h: t("Reason"), f: (r) => r.reason }]} />
            </Card>
          </Grid>
          <Activity id={id} write={write} />
          <Muted>{t("Edits are recorded as administrative activity and are visible to compliance monitoring.")}</Muted>
        </>
      );
    }}</Query>
  );
}
