import { useNavigate } from "react-router-dom";
import { DataTable } from "../../components/DataTable";
import { Query } from "../../components/Query";
import { Card, Status } from "../../components/ui";
import { num, pct, t } from "../../lib/i18n";

export default function Supervisees() {
  const navigate = useNavigate();
  return (
    <Query path="/supervision/supervisees">{(rows) => (
      <Card title={t("Supervisees")}>
        <DataTable rows={rows} onRow={(r) => navigate(`/supervision/supervisees/${r.id}`)} columns={[{ h: t("Name"), f: (r) => r.name }, { h: t("Status"), f: (r) => <Status status={r.status} /> },
          { h: t("Pending"), f: (r) => num(r.pending_reviews) }, { h: t("Overdue"), f: (r) => num(r.overdue_reviews) }, { h: t("Avg score"), f: (r) => num(r.avg_performance) },
          { h: t("Meeting attendance"), f: (r) => pct(r.meeting_attendance) }, { h: t("Every"), f: (r) => t("{0} d", num(r.schedule_every_days)) }]} />
      </Card>
    )}</Query>
  );
}
