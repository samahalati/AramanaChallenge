import { Route, Routes } from "react-router-dom";
import { t } from "../../lib/i18n";
import { Page } from "../../components/Query";
import { Tabs } from "../../components/ui";
import Dashboard from "./Dashboard";
import Issues from "./Issues";
import ReviewDetail from "./ReviewDetail";
import Reviews from "./Reviews";
import SuperviseeDetail from "./SuperviseeDetail";
import Supervisees from "./Supervisees";

export default function Supervision() {
  return (
    <Page title={t("Clinical supervision & quality")} sub={t("Your assigned practitioners only. Every record you open is audited. Clinical decisions remain with qualified humans.")}>
      <Tabs items={[["/supervision", t("Dashboard")], ["/supervision/supervisees", t("Supervisees")], ["/supervision/reviews", t("Reviews")], ["/supervision/issues", t("Quality issues")]]} />
      <Routes>
        <Route index element={<Dashboard />} />
        <Route path="supervisees" element={<Supervisees />} />
        <Route path="supervisees/:id" element={<SuperviseeDetail />} />
        <Route path="reviews" element={<Reviews />} />
        <Route path="reviews/:id" element={<ReviewDetail />} />
        <Route path="issues" element={<Issues />} />
      </Routes>
    </Page>
  );
}
