import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useGet } from "../../api/hooks";
import { DataTable } from "../../components/DataTable";
import { Card, Level, Muted, Status } from "../../components/ui";
import { qs } from "../../lib/format";
import { dt, num, pretty, t } from "../../lib/i18n";
import { Select } from "../hr/Practitioners";

const opt = (values) => values.map((v) => [v, pretty(v)]);
const FILTERS = {
  level: [["", t("Any risk")], ...opt(["critical", "high", "medium", "low"])],
  status: [["", t("Any status")], ...opt(["new", "under_review", "info_requested", "escalated", "false_positive", "closed_substantiated", "closed_no_action"])],
  category: [["", t("Any category")], ["A", t("A Therapist")], ["B", t("B Counselor")], ["C", t("C Supervisor")], ["D", t("D Admin/platform")], ["E", t("E Network")], ["Q", t("Q Escalation")]],
  domain: [["", t("Any domain")], ...opt(["operational", "clinical", "misconduct", "security"])],
};

export default function AlertList() {
  const [f, setF] = useState({ level: "", status: "", category: "", domain: "" });
  const { data } = useGet(`/alerts?limit=200&${qs(f)}`);
  const navigate = useNavigate();
  return (
    <Card>
      <div className="row" style={{ marginBottom: 10 }}>{Object.entries(FILTERS).map(([k, options]) => <Select key={k} value={f[k]} onChange={(v) => setF({ ...f, [k]: v })} options={options} />)}</div>
      <Muted>{t("{0} alerts", num(data?.total ?? 0))}</Muted>
      <DataTable rows={data?.items} onRow={(a) => navigate(`/monitoring/alerts/${a.id}`)} columns={[{ h: t("ID"), f: (a) => <span dir="ltr">{a.alert_uid}</span> }, { h: t("Risk"), f: (a) => <span><Level level={a.risk_level} /> {num(Math.round(a.risk_score))}</span> },
        { h: t("Alert"), f: (a) => a.title }, { h: t("Cat."), f: (a) => a.category }, { h: t("Domain"), f: (a) => pretty(a.domain) }, { h: t("Methods"), f: (a) => a.methods.map(pretty).join("، ") }, { h: t("Status"), f: (a) => <Status status={a.status} /> },
        { h: t("Detected"), f: (a) => dt(a.detected_at) }]} />
    </Card>
  );
}
