import { Link } from "react-router-dom";
import { DataTable } from "../../components/DataTable";
import { Query } from "../../components/Query";
import { Card, Grid, Kpi, LineChart } from "../../components/ui";
import { d10, dt, num, pretty, t } from "../../lib/i18n";

export default function Dashboard() {
  return (
    <Query path="/supervision/dashboard">{(d) => (
      <>
        <Grid cols={4}>
          <Kpi n={d.supervisees_total} label={t("Assigned supervisees")} /><Kpi n={`${num(d.active)} / ${num(d.inactive)}`} label={t("Active / inactive")} />
          <Kpi n={d.pending_reviews} label={t("Pending reviews")} /><Kpi n={d.overdue_reviews} label={t("Overdue reviews")} tone={d.overdue_reviews ? "critical" : ""} />
          <Kpi n={d.open_quality_issues} label={t("Open quality issues")} /><Kpi n={d.cases_requiring_escalation} label={t("Cases needing escalation")} /><Kpi n={d.escalated_cases} label={t("Escalated")} />
        </Grid>
        <Grid style={{ marginTop: 14 }}>
          <Card title={t("Performance trend (avg review score)")}><LineChart points={d.performance_trend} field="avg_score" caption={t("Average performance score (1–5) of reviews decided per week")} /></Card>
          <Card title={t("Overdue reviews")}>
            <DataTable rows={d.overdue_list} columns={[{ h: t("Supervisee"), f: (r) => r.supervisee }, { h: t("Case"), f: (r) => <Link to={`/supervision/reviews/${r.id}`}>{r.case_ref}</Link> }, { h: t("Due"), f: (r) => d10(r.due_date) }]} />
          </Card>
          <Card title={t("Recent supervision activity")}>
            <DataTable rows={d.recent_activity} columns={[{ h: t("When"), f: (r) => dt(r.ts) }, { h: t("Type"), f: (r) => pretty(r.type) }, { h: t("Supervisee"), f: (r) => r.supervisee }, { h: t("Case"), f: (r) => r.case_ref }]} />
          </Card>
        </Grid>
      </>
    )}</Query>
  );
}
