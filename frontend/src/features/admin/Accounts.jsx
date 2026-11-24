import { Route, Routes } from "react-router-dom";
import { patch, post } from "../../api/client";
import { useAct, useGet } from "../../api/hooks";
import { DataTable } from "../../components/DataTable";
import { useForm } from "../../components/FormModal";
import { Page, Query } from "../../components/Query";
import { Card, Muted, Status, Tabs } from "../../components/ui";
import { dt, num, pretty, t } from "../../lib/i18n";

const ROLES = ["therapist", "assistant_counselor", "clinical_supervisor", "hr_admin", "compliance_reviewer", "platform_admin"].map((r) => [r, pretty(r)]);

function Users() {
  const ask = useForm(), act = useAct();
  const create = () => ask({ title: t("Create account"), submit: t("Create"), fields: [{ name: "full_name", label: t("Full name") }, { name: "email", label: t("E-mail") }, { name: "role", label: t("Role"), type: "select", options: ROLES }, { name: "password", label: t("Initial password (≥10)"), type: "password" }],
    onSubmit: (v) => act(() => post("/admin/users", v), t("Account created")) });
  const changeRole = (u) => ask({ title: t("Change role: {0}", u.full_name), submit: t("Change"), fields: [{ name: "role", label: t("New role"), type: "select", value: u.role, options: ROLES }, { name: "reason", label: t("Reason"), type: "textarea" }],
    onSubmit: (v) => act(() => patch(`/admin/users/${u.id}/role`, v), t("Role changed")) });
  const changeStatus = (u) => ask({ title: t("Change status: {0}", u.full_name), submit: t("Apply"), fields: [{ name: "status", label: t("Status"), type: "select", value: u.status === "active" ? "suspended" : "active", options: [["active", pretty("active")], ["suspended", pretty("suspended")]] }, { name: "reason", label: t("Reason"), type: "textarea" }],
    onSubmit: (v) => act(() => patch(`/admin/users/${u.id}/status`, v), t("Status changed")) });
  return (
    <Query path="/admin/users">{(rows) => (
      <Card title={t("Platform accounts")} action={<button className="primary" onClick={create}>{t("+ New account")}</button>}>
        <Muted>{t("Role and status changes are audited and monitored. You cannot change your own role.")}</Muted>
        <DataTable rows={rows} columns={[{ h: t("Name"), f: (r) => r.full_name }, { h: t("E-mail"), f: (r) => <span dir="ltr">{r.email}</span> }, { h: t("Role"), f: (r) => pretty(r.role) }, { h: t("Status"), f: (r) => <Status status={r.status} /> },
          { h: "", f: (r) => <span className="row"><a onClick={() => changeRole(r)}>{t("role")}</a><a onClick={() => changeStatus(r)}>{t("status")}</a></span> }]} />
      </Card>
    )}</Query>
  );
}

function Activity() {
  const { data } = useGet("/admin/activity?limit=100");
  return <Card title={t("Administrative activity log")}><DataTable rows={data} columns={[{ h: t("Time"), f: (r) => dt(r.ts) }, { h: t("Actor"), f: (r) => `#${num(r.actor_id)}` }, { h: t("Action"), f: (r) => pretty(r.action) }, { h: t("Target"), f: (r) => (r.target_user_id ? `#${num(r.target_user_id)}` : "–") }, { h: t("Detail"), f: (r) => <span dir="ltr">{JSON.stringify(r.detail || {}).slice(0, 90)}</span> }]} /></Card>;
}

export default function Accounts() {
  return (
    <Page title={t("Platform accounts")} sub={t("Account administration. This role has no access to HR record content or clinical data (separation of duties).")}>
      <Tabs items={[["/admin", t("Accounts")], ["/admin/activity", t("Admin activity")]]} />
      <Routes><Route index element={<Users />} /><Route path="activity" element={<Activity />} /></Routes>
    </Page>
  );
}
