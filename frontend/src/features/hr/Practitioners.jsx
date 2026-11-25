import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { post } from "../../api/client";
import { useAct, useGet } from "../../api/hooks";
import { useAuth } from "../../auth/AuthContext";
import { DataTable } from "../../components/DataTable";
import { useForm } from "../../components/FormModal";
import { Card, Status } from "../../components/ui";
import { qs } from "../../lib/format";
import { pretty, t } from "../../lib/i18n";

export const SPECS = ["trauma", "anxiety", "depression", "couples", "child", "addiction"];
const ROLES = ["therapist", "assistant_counselor", "clinical_supervisor"].map((r) => [r, pretty(r)]);
const STATUSES = ["active", "pending_onboarding", "suspended", "terminated"].map((s) => [s, pretty(s)]);
const withAll = (label, options) => [["", label], ...options];

export function Select({ value, onChange, options }) {
  return <select value={value} onChange={(e) => onChange(e.target.value)}>{options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>;
}

export default function Practitioners() {
  const [f, setF] = useState({ q: "", role: "", status: "" });
  const { data: rows } = useGet(`/hr/practitioners?${qs(f)}`);
  const { can } = useAuth();
  const ask = useForm(), act = useAct(), navigate = useNavigate();
  const create = () => ask({
    title: t("New practitioner (pending onboarding)"), submit: t("Create"),
    fields: [{ name: "full_name", label: t("Full name") }, { name: "email", label: t("E-mail") }, { name: "role", label: t("Role"), type: "select", options: ROLES },
      { name: "specialization", label: t("Specialisation"), type: "select", options: withAll("–", SPECS.map((s) => [s, pretty(s)])) },
      { name: "capacity_weekly_sessions", label: t("Weekly capacity"), type: "number", value: 25 }, { name: "initial_password", label: t("Initial password (≥10 chars)"), type: "password" }],
    onSubmit: async (v) => { await act(() => post("/hr/practitioners", { ...v, specialization: v.specialization || null }), t("Practitioner created")); },
  });
  return (
    <Card>
      <div className="row" style={{ marginBottom: 12 }}>
        <input placeholder={t("Search name or e-mail…")} value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} />
        <Select value={f.role} onChange={(role) => setF({ ...f, role })} options={withAll(t("All roles"), ROLES)} />
        <Select value={f.status} onChange={(status) => setF({ ...f, status })} options={withAll(t("Any status"), STATUSES)} />
        {can("hr:write") && <button className="primary" onClick={create}>{t("+ New practitioner")}</button>}
      </div>
      <DataTable rows={rows} onRow={(r) => navigate(`/hr/practitioners/${r.id}`)} columns={[{ h: t("Name"), f: (r) => r.full_name }, { h: t("Role"), f: (r) => pretty(r.role) },
        { h: t("Specialisation"), f: (r) => (r.specialization ? pretty(r.specialization) : "–") }, { h: t("Unit"), f: (r) => r.org_unit || "–" }, { h: t("Employment"), f: (r) => pretty(r.employment_type) }, { h: t("Status"), f: (r) => <Status status={r.status} /> }]} />
    </Card>
  );
}
