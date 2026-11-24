import { Query } from "../../components/Query";
import { Card } from "../../components/ui";
import { num, pretty, t } from "../../lib/i18n";

function Node({ unit, all }) {
  const children = all.filter((u) => u.parent_id === unit.id);
  return <li><b>{unit.name}</b> ({pretty(unit.kind)}، {t("{0} members", num(unit.members))}){children.length > 0 && <ul>{children.map((c) => <Node key={c.id} unit={c} all={all} />)}</ul>}</li>;
}

export default function OrgTree() {
  return <Query path="/hr/org-units">{(units) => <Card title={t("Organisational hierarchy")}><ul>{units.filter((u) => !u.parent_id).map((u) => <Node key={u.id} unit={u} all={units} />)}</ul></Card>}</Query>;
}
