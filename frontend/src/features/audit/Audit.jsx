import { Route, Routes } from "react-router-dom";
import { useGet } from "../../api/hooks";
import { DataTable } from "../../components/DataTable";
import { Page } from "../../components/Query";
import { Badge, Card, Tabs } from "../../components/ui";
import { dt, num, pretty, t } from "../../lib/i18n";

function Log() {
  const { data: rows } = useGet("/audit?limit=150");
  const { data: v } = useGet("/audit/verify");
  return (
    <Card>
      <div className="row" style={{ marginBottom: 10 }}><h2 style={{ margin: 0 }}>{t("Hash-chained audit log")}</h2>{v && <Badge tone={v.ok ? "ok" : "critical"}>{v.ok ? t("chain verified ({0} entries)", num(v.checked)) : t("TAMPERING at #{0}", num(v.first_bad_id))}</Badge>}</div>
      <DataTable rows={rows} columns={[{ h: "#", f: (r) => num(r.id) }, { h: t("Time"), f: (r) => dt(r.ts) }, { h: t("Actor"), f: (r) => (r.actor_id ? `#${num(r.actor_id)}` : t("system")) }, { h: t("Action"), f: (r) => pretty(r.action) },
        { h: t("Resource"), f: (r) => `${pretty(r.resource_type)} ${r.resource_id || ""}` }, { h: t("Outcome"), f: (r) => <Badge tone={r.outcome === "ok" ? "ok" : "high"}>{pretty(r.outcome)}</Badge> }, { h: t("Hash"), f: (r) => <code dir="ltr">{r.hash}</code> }]} />
    </Card>
  );
}

function Denied() {
  const { data: rows } = useGet("/audit/access-events?event=access_denied&limit=150");
  return <Card title={t("Denied access events")}><DataTable rows={rows} columns={[{ h: t("Time"), f: (r) => dt(r.ts) }, { h: t("User"), f: (r) => `#${num(r.user_id)}` }, { h: t("Permission"), f: (r) => pretty(r.permission) }, { h: t("Path"), f: (r) => <span dir="ltr">{r.path}</span> }, { h: t("IP"), f: (r) => <span dir="ltr">{r.ip}</span> }]} /></Card>;
}

export default function Audit() {
  return (
    <Page title={t("Audit & access events")} sub={t("Who accessed what, when, with what outcome. Each row commits to the previous row's hash.")}>
      <Tabs items={[["/audit", t("Audit log")], ["/audit/denied", t("Denied access")]]} />
      <Routes><Route index element={<Log />} /><Route path="denied" element={<Denied />} /></Routes>
    </Page>
  );
}
