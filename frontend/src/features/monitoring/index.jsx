import { Route, Routes } from "react-router-dom";
import { t } from "../../lib/i18n";
import { Page } from "../../components/Query";
import { Tabs } from "../../components/ui";
import AlertDetail from "./AlertDetail";
import AlertList from "./AlertList";
import Config from "./Config";
import Overview from "./Overview";

export default function Monitoring() {
  return (
    <Page title={t("Fraud & anomaly monitoring")} sub={t("Rules · robust statistics · Isolation Forest · graph analysis · AI-assisted briefing. Alerts are advisory – only authorised humans decide.")}>
      <Tabs items={[["/monitoring", t("Overview")], ["/monitoring/alerts", t("Alerts")], ["/monitoring/config", t("Scoring & evaluation")]]} />
      <Routes>
        <Route index element={<Overview />} />
        <Route path="alerts" element={<AlertList />} />
        <Route path="alerts/:id" element={<AlertDetail />} />
        <Route path="config" element={<Config />} />
      </Routes>
    </Page>
  );
}
