import { post } from "../../api/client";
import { useAct, useGet } from "../../api/hooks";
import { DataTable } from "../../components/DataTable";
import { useForm } from "../../components/FormModal";
import { Query } from "../../components/Query";
import { Card, Muted, Status } from "../../components/ui";
import { pretty, t } from "../../lib/i18n";

export default function Issues() {
  const { data: subs = [] } = useGet("/supervision/supervisees");
  const ask = useForm(), act = useAct();
  const record = () => ask({
    title: t("Record quality issue"), submit: t("Record"),
    fields: [{ name: "practitioner_id", label: t("Practitioner"), type: "select", options: subs.map((s) => [s.id, s.name]) },
      { name: "category", label: t("Category"), type: "select", options: [["operational", t("Operational alert")], ["clinical", t("Clinical concern")], ["misconduct", pretty("misconduct")]] },
      { name: "title", label: t("Title") }, { name: "detail", label: t("Detail"), type: "textarea" }, { name: "severity", label: t("Severity"), type: "select", value: "medium", options: ["low", "medium", "high"].map((x) => [x, pretty(x)]) }],
    onSubmit: (v) => act(() => post("/supervision/quality-issues", { ...v, practitioner_id: +v.practitioner_id }), t("Issue recorded")),
  });
  const escalate = (i) => ask({ title: t("Escalate to compliance"), submit: t("Escalate"), fields: [{ name: "reason", label: t("Why does this need additional review?"), type: "textarea" }],
    onSubmit: (v) => act(() => post(`/supervision/quality-issues/${i.id}/escalate`, v), (x) => t("Escalated as {0}", x.alert_uid)) });
  return (
    <Query path="/supervision/quality-issues">{(rows) => (
      <Card title={t("Quality issues & escalation")} action={<button className="primary" onClick={record}>{t("+ Record issue")}</button>}>
        <Muted>{t("Operational alerts, clinical concerns and potential misconduct are kept distinct. Escalation creates a traceable alert for compliance.")}</Muted>
        <DataTable rows={rows} columns={[{ h: t("Practitioner"), f: (r) => r.practitioner }, { h: t("Category"), f: (r) => pretty(r.category) }, { h: t("Title"), f: (r) => r.title }, { h: t("Sev."), f: (r) => pretty(r.severity) },
          { h: t("Status"), f: (r) => <Status status={r.status} /> },
          { h: "", f: (r) => r.status === "open" && <span className="row"><a onClick={() => escalate(r)}>{t("escalate")}</a><a onClick={() => act(() => post(`/supervision/quality-issues/${r.id}/resolve`), t("Resolved"))}>{t("resolve")}</a></span> }]} />
      </Card>
    )}</Query>
  );
}
