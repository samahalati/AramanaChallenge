import { useState } from "react";
import { Link } from "react-router-dom";
import { useGet } from "../../api/hooks";
import { DataTable } from "../../components/DataTable";
import { Badge, Card, Status } from "../../components/ui";
import { qs } from "../../lib/format";
import { d10, pretty, t } from "../../lib/i18n";
import { Select } from "../hr/Practitioners";

const STATES = [["", t("All")], ...["pending", "in_progress", "needs_changes", "approved"].map((s) => [s, pretty(s)])];

export default function Reviews() {
  const [status, setStatus] = useState(""), [overdue, setOverdue] = useState(false);
  const { data: rows } = useGet(`/supervision/reviews?${qs({ status, overdue: overdue || "" })}`);
  return (
    <Card>
      <div className="row" style={{ marginBottom: 10 }}>
        <h2 style={{ margin: 0 }}>{t("Reviews")}</h2><Select value={status} onChange={setStatus} options={STATES} />
        <label style={{ margin: 0 }}><input type="checkbox" style={{ width: "auto" }} checked={overdue} onChange={(e) => setOverdue(e.target.checked)} /> {t("overdue only")}</label>
      </div>
      <DataTable rows={rows} columns={[{ h: t("Case"), f: (r) => <Link to={`/supervision/reviews/${r.id}`}>{r.case_ref}</Link> }, { h: t("Supervisee"), f: (r) => r.supervisee },
        { h: t("Status"), f: (r) => <Status status={r.status} /> }, { h: t("Due"), f: (r) => d10(r.due_date) }, { h: "", f: (r) => r.overdue && <Badge tone="critical">{t("overdue")}</Badge> }]} />
    </Card>
  );
}
