import { Link } from "react-router-dom";
import { post } from "../../api/client";
import { useAct, useGet } from "../../api/hooks";
import { useAuth } from "../../auth/AuthContext";
import { DataTable } from "../../components/DataTable";
import { useForm } from "../../components/FormModal";
import { Card } from "../../components/ui";
import { d10, today } from "../../lib/format";
import { num, t } from "../../lib/i18n";

export default function Assignments() {
  const { data: rows } = useGet("/hr/assignments");
  const { data: sups = [] } = useGet("/hr/practitioners?role=clinical_supervisor&status=active");
  const { data: subs = [] } = useGet("/hr/practitioners?status=active");
  const { can } = useAuth();
  const ask = useForm(), act = useAct();
  const assign = () => ask({
    title: t("Assign / reassign supervisor"), submit: t("Assign"),
    fields: [{ name: "supervisee_id", label: t("Supervisee"), type: "select", options: subs.filter((s) => s.role !== "clinical_supervisor").map((s) => [s.id, s.full_name]) },
      { name: "supervisor_id", label: t("New supervisor"), type: "select", options: sups.map((s) => [s.id, s.full_name]) }, { name: "effective_from", label: t("Effective from"), type: "date", value: today() },
      { name: "reason", label: t("Reason"), type: "textarea" }, { name: "schedule_every_days", label: t("Supervision every (days)"), type: "number", value: 7 }],
    onSubmit: (v) => act(() => post("/hr/assignments", { ...v, supervisee_id: +v.supervisee_id, supervisor_id: +v.supervisor_id, schedule_every_days: v.schedule_every_days ?? 7 }), t("Assignment saved – previous relationship end-dated")),
  });
  return (
    <Card title={t("Current supervisor–supervisee relationships")} action={can("hr:write") && <button className="primary" onClick={assign}>{t("+ Assign / reassign")}</button>}>
      <DataTable rows={rows} columns={[{ h: t("Supervisor"), f: (r) => r.supervisor }, { h: t("Supervisee"), f: (r) => <Link to={`/hr/practitioners/${r.supervisee_id}`}>{r.supervisee}</Link> },
        { h: t("Since"), f: (r) => d10(r.effective_from) }, { h: t("Schedule"), f: (r) => t("every {0} d", num(r.schedule_every_days)) }]} />
    </Card>
  );
}
