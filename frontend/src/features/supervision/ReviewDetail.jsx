import { Link, useParams } from "react-router-dom";
import { post } from "../../api/client";
import { useAct } from "../../api/hooks";
import { DataTable } from "../../components/DataTable";
import { useForm } from "../../components/FormModal";
import { Query } from "../../components/Query";
import { Badge, Card, Status } from "../../components/ui";
import { inDays } from "../../lib/format";
import { d10, dt, isFa, num, pretty, t } from "../../lib/i18n";

export default function ReviewDetail() {
  const { id } = useParams();
  const ask = useForm(), act = useAct(), base = `/supervision/reviews/${id}`;
  return (
    <Query path={base}>{(r) => {
      const decided = ["approved", "needs_changes"].includes(r.status);
      const decide = () => ask({
        title: t("Record evaluation & outcome"), submit: t("Record decision"), intro: t("Approvals without documentation are allowed but flagged to compliance monitoring."),
        fields: [{ name: "outcome", label: t("Outcome"), type: "select", options: [["approved", pretty("approved")], ["needs_changes", pretty("needs_changes")]] }, { name: "notes", label: t("Supervision notes"), type: "textarea" },
          { name: "feedback", label: t("Feedback to practitioner"), type: "textarea" }, { name: "performance_score", label: t("Performance (1–5)"), type: "number", value: 4 },
          { name: "has_documentation", label: t("Supporting documentation reviewed & attached"), type: "checkbox", value: true }, { name: "minutes_spent", label: t("Minutes spent (optional)"), type: "number" }],
        onSubmit: async (v) => { await act(() => post(`${base}/decision`, v), (res) => res.warning || t("Decision recorded")); },
      });
      const corrective = () => ask({ title: t("Assign corrective action"), submit: t("Assign"), fields: [{ name: "description", label: t("Action"), type: "textarea" }, { name: "due_date", label: t("Due"), type: "date", value: inDays(14) }],
        onSubmit: (v) => act(() => post(`${base}/corrective-actions`, v), t("Corrective action assigned")) });
      const close = () => ask({ title: t("Close review"), submit: t("Close"), fields: [{ name: "monitoring_plan", label: t("Monitoring / improvement plan (required if actions are open)"), type: "textarea" }],
        onSubmit: (v) => act(() => post(`${base}/close`, v), t("Review closed")) });
      return (
        <>
          <p><Link to="/supervision/reviews">{isFa ? "→" : "←"} {t("Reviews")}</Link></p>
          <Card>
            <div className="row between">
              <h2>{r.case_ref} · {r.supervisee} <Status status={r.status} /> {r.closed_at && <Badge>{t("closed")}</Badge>} {r.overdue && <Badge tone="critical">{t("overdue")}</Badge>}</h2>
              <div className="row">
                {r.status === "pending" && <button onClick={() => act(() => post(`${base}/start`), t("Review started"))}>{t("Start review")}</button>}
                {!decided && !r.closed_at && <button className="primary" onClick={decide}>{t("Record decision")}</button>}
                {decided && !r.closed_at && <><button onClick={corrective}>{t("+ Corrective action")}</button><button onClick={close}>{t("Close review")}</button></>}
              </div>
            </div>
            <p className="muted">{t("Due {0}", d10(r.due_date))} · {t("decided {0}", dt(r.decided_at))} · {t("documentation {0}", r.has_documentation ? t("yes") : t("no"))} · {t("score {0}", num(r.performance_score))} · {t("{0} min", num(r.decision_minutes))}</p>
            <h3>{t("Supervision notes")}</h3><p>{r.supervision_notes || "–"}</p>
            <h3>{t("Feedback")}</h3><p>{r.feedback || "–"}</p>
            <h3>{t("Corrective actions")}</h3>
            <DataTable rows={r.corrective_actions} columns={[{ h: t("Action"), f: (a) => a.description }, { h: t("Due"), f: (a) => d10(a.due_date) }, { h: t("Status"), f: (a) => <Status status={a.status} /> }]} />
          </Card>
        </>
      );
    }}</Query>
  );
}
