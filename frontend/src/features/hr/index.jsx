import { Route, Routes } from "react-router-dom";
import { t } from "../../lib/i18n";
import { Page } from "../../components/Query";
import { Tabs } from "../../components/ui";
import Assignments from "./Assignments";
import Dashboard from "./Dashboard";
import OrgTree from "./OrgTree";
import PractitionerDetail from "./PractitionerDetail";
import Practitioners from "./Practitioners";

export default function Hr() {
  return (
    <Page title={t("HR & platform administration")} sub={t("Workforce, credentials, contracts, lifecycle and organisational structure. Contains no clinical data.")}>
      <Tabs items={[["/hr", t("Dashboard")], ["/hr/practitioners", t("Practitioners")], ["/hr/assignments", t("Supervision assignments")], ["/hr/org", t("Organisation")]]} />
      <Routes>
        <Route index element={<Dashboard />} />
        <Route path="practitioners" element={<Practitioners />} />
        <Route path="practitioners/:id" element={<PractitionerDetail />} />
        <Route path="assignments" element={<Assignments />} />
        <Route path="org" element={<OrgTree />} />
      </Routes>
    </Page>
  );
}
