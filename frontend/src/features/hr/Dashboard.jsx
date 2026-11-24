import { Link } from "react-router-dom";
import { DataTable } from "../../components/DataTable";
import { Query } from "../../components/Query";
import { Badge, Bars, Card, Grid, Kpi } from "../../components/ui";
import { d10, num, pretty, t } from "../../lib/i18n";

const person = (r) => <Link to={`/hr/practitioners/${r.user_id}`}>{r.practitioner}</Link>;

export default function Dashboard() {
  return (
    <Query path="/hr/dashboard">{(d) => (
      <>
        <Grid cols={4}>
          <Kpi n={d.practitioners_by_status.active || 0} label={t("Active")} />
          <Kpi n={d.practitioners_by_status.pending_onboarding || 0} label={t("Pending onboarding")} />
          <Kpi n={d.practitioners_by_status.suspended || 0} label={t("Suspended")} />
          <Kpi n={d.practitioners_by_status.terminated || 0} label={t("Terminated")} />
          <Kpi n={d.unassigned_supervisees} label={t("Therapists without supervisor")} />
        </Grid>
        <Grid style={{ marginTop: 14 }}>
          <Card title={t("Credentials expiring ≤ 60 days or expired")}>
            <DataTable rows={d.credentials_expiring_or_expired} columns={[{ h: t("Practitioner"), f: person }, { h: t("Credential"), f: (r) => r.title }, { h: t("Expires"), f: (r) => d10(r.expires_on) },
              { h: t("Days"), f: (r) => <Badge tone={r.days_to_expiry < 0 ? "critical" : "medium"}>{num(r.days_to_expiry)}</Badge> }]} />
          </Card>
          <Card title={t("Contracts ending soon")}>
            <DataTable rows={d.contracts_ending_soon} columns={[{ h: t("Practitioner"), f: person }, { h: t("Type"), f: (r) => pretty(r.kind) }, { h: t("Ends"), f: (r) => d10(r.end_date) }]} />
          </Card>
          <Card title={t("Recent lifecycle events")}>
            <DataTable rows={d.recent_lifecycle} columns={[{ h: t("Who"), f: (r) => r.practitioner }, { h: t("Event"), f: (r) => pretty(r.event) }, { h: t("Date"), f: (r) => d10(r.date) }, { h: t("Reason"), f: (r) => r.reason }]} />
          </Card>
          <Card title={t("By role")}><Bars data={d.practitioners_by_role} /></Card>
        </Grid>
      </>
    )}</Query>
  );
}
