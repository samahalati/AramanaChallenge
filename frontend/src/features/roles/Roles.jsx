import { DataTable } from "../../components/DataTable";
import { Page, Query } from "../../components/Query";
import { Card } from "../../components/ui";
import { pretty, t } from "../../lib/i18n";

export default function Roles() {
  return (
    <Page title={t("Roles & permission matrix")} sub={t("Exactly what the API enforces (same data). Clinical and HR data are separated: administrative roles hold no clinical permission.")}>
      <Query path="/meta/rbac">{(r) => (
        <Card><DataTable rows={r.roles.map((x) => ({ ...x, id: x.role }))} columns={[{ h: t("Role"), f: (x) => <div><b>{pretty(x.role)}</b><div className="small muted">{x.description}</div></div> },
          { h: t("Permissions"), f: (x) => x.permissions.map(pretty).join("، ") }, { h: t("Sees alerts of"), f: (x) => x.alert_domains_visible.map(pretty).join("، ") || "–" }, { h: t("May investigate"), f: (x) => x.alert_domains_investigate.map(pretty).join("، ") || "–" }]} /></Card>
      )}</Query>
    </Page>
  );
}
