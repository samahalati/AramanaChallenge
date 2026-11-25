import { post } from "../../api/client";
import { useAct } from "../../api/hooks";
import { useAuth } from "../../auth/AuthContext";
import { DataTable } from "../../components/DataTable";
import { Query } from "../../components/Query";
import { Bars, Card, Grid, Kpi, Muted } from "../../components/ui";
import { d10, dt, num, pct, pretty, t } from "../../lib/i18n";

export const LEVEL_COLOR = { low: "var(--low)", medium: "var(--medium)", high: "var(--high)", critical: "var(--critical)" };

export default function Overview() {
  const { can } = useAuth();
  const act = useAct();
  const run = () => act(() => post("/detection/run"), (r) => t("Detection run #{0}: {1} new, {2} updated", num(r.run_id), num(r.alerts_created), num(r.alerts_updated)));
  return (
    <Query path="/monitoring/summary">{(s) => (
      <>
        <div className="row between" style={{ marginBottom: 12 }}>
          <span className="muted">{s.last_run ? t("Last run #{0} · {1} · {2} · data as of {3}", num(s.last_run.id), s.last_run.ruleset_version, s.last_run.model_version, dt(s.last_run.as_of)) : t("No detection run yet")}</span>
          {can("detection:run") && <button className="primary" onClick={run}>{t("▶ Run detection now")}</button>}
        </div>
        <Grid cols={4}><Kpi n={s.total} label={t("Alerts visible to you")} /><Kpi n={s.open} label={t("Open")} /><Kpi n={s.by_level.critical} label={t("Critical")} tone="critical" /><Kpi n={s.by_level.high} label={t("High")} tone="high" /></Grid>
        <Grid style={{ marginTop: 14 }}>
          <Card title={t("By risk level")}><Bars data={s.by_level} color={(k) => LEVEL_COLOR[k]} /></Card>
          <Card title={t("By domain")}><Bars data={s.by_domain} /><Muted>{t("Operational alerts, clinical concerns, potential misconduct and security events are routed to different roles.")}</Muted></Card>
          <Card title={t("By status")}><Bars data={s.by_status} /></Card>
          <Card title={t("Alerts over time (week of detection)")}><Bars data={Object.fromEntries(s.weekly_trend.map((w) => [d10(w.week), w.alerts]))} /></Card>
          <Card title={t("False-positive feedback")}><Muted>{t("Closed alerts by scenario – investigators' outcomes feed rule tuning.")}</Muted>
            <DataTable rows={s.false_positive_feedback.map((r) => ({ ...r, id: r.scenario }))} columns={[{ h: t("Scenario"), f: (r) => pretty(r.scenario) }, { h: t("Closed"), f: (r) => num(r.closed) }, { h: t("False +"), f: (r) => num(r.false_positive) }, { h: t("FP rate"), f: (r) => pct(r.fp_rate) }]} />
          </Card>
          {s.last_run?.suppressed.length > 0 && (
            <Card title={t("Suppressed: explained by policy")}>
              <Muted>{t("These counselors look concentrated against a naive baseline, but their referrals match what specialisation/assignment policy predicts, so no alert was raised.")}</Muted>
              <DataTable rows={s.last_run.suppressed.map((r) => ({ ...r, id: r.counselor }))} columns={[{ h: t("Counselor"), f: (r) => `#${num(r.counselor)}` }, { h: t("Naive p"), f: (r) => num(r.naive_p) }, { h: t("Policy-aware p"), f: (r) => num(r.policy_aware_p) },
                { h: t("Top share vs policy-expected"), f: (r) => r.top_therapists.slice(0, 2).map((x, i) => <div key={i}>{t("{0} vs {1}", pct(x.share), pct(x.policy_expected_share))}</div>) }]} />
            </Card>
          )}
        </Grid>
      </>
    )}</Query>
  );
}
