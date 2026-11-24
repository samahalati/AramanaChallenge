import { useGet } from "../../api/hooks";
import { useAuth } from "../../auth/AuthContext";
import { DataTable } from "../../components/DataTable";
import { Query } from "../../components/Query";
import { Card, Grid, Muted } from "../../components/ui";
import { num, pretty, t } from "../../lib/i18n";

function Evaluation() {
  const { data: ev } = useGet("/detection/evaluation");
  if (!ev?.available) return null;
  const o = ev.overall;
  return (
    <Card title={t("Measured performance on the synthetic dataset")}>
      <Muted>{t("Evaluation unit = (user, category); alerts ≥ {0}; seed {1}. Ground truth is synthetic and injected – real-world performance will differ.", pretty(ev.min_level), num(ev.seed))}</Muted>
      <p><b>{t("Precision {0} · Recall {1} · F1 {2}", num(o.precision), num(o.recall), num(o.f1))}</b> ({t("tp {0}, fp {1}, fn {2}", num(o.tp), num(o.fp), num(o.fn))}); {t("hard-negative false positives: {0}/{1}", num(ev.hard_negatives.false_positives_at_min_level), num(ev.hard_negatives.n))}</p>
      <h3>{t("Ablation by detection layer")}</h3>
      <DataTable rows={Object.entries(ev.ablation).map(([k, m]) => ({ id: k, k, ...m }))} columns={[{ h: t("Layers"), f: (r) => pretty(r.k) }, { h: t("Precision"), f: (r) => num(r.precision) }, { h: t("Recall"), f: (r) => num(r.recall) }, { h: "F1", f: (r) => num(r.f1) }]} />
      <h3>{t("Per scenario")}</h3>
      <DataTable rows={Object.entries(ev.per_scenario).map(([k, m]) => ({ id: k, k, ...m }))} columns={[{ h: t("Scenario"), f: (r) => pretty(r.k) }, { h: t("Detected"), f: (r) => `${num(r.detected)}/${num(r.of)}` }]} />
    </Card>
  );
}

export default function Config() {
  const { can } = useAuth();
  return (
    <Query path="/detection/config">{(cfg) => (
      <Grid>
        <Card title={t("Active configuration")}>
          <Muted>{t("ruleset {0}", cfg.ruleset_version)} · {t("risk levels")}: {Object.entries(cfg.risk.levels).map(([k, v]) => `${pretty(k)} ≥ ${num(v)}`).join("، ")}</Muted>
          <h3>{t("Indicator weights (max contribution)")}</h3>
          <DataTable rows={Object.entries(cfg.weights).map(([k, v]) => ({ id: k, k, v }))} columns={[{ h: t("Indicator"), f: (r) => pretty(r.k) }, { h: t("Weight"), f: (r) => num(r.v) }]} />
          <Muted>{t("score = 100 × (1 − Π(1 − weight × strength)). Alerts supported only by weak indicators (ML score, volume) are capped at Low.")}</Muted>
        </Card>
        {can("detection:run") && <Evaluation />}
      </Grid>
    )}</Query>
  );
}
