import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { t } from "./lib/i18n";
import Layout from "./components/Layout";
import Admin from "./features/admin/Accounts";
import Audit from "./features/audit/Audit";
import Hr from "./features/hr";
import Login from "./features/login/Login";
import Monitoring from "./features/monitoring";
import MyWork from "./features/mywork/MyWork";
import Roles from "./features/roles/Roles";
import Supervision from "./features/supervision";

/** Each feature is a lazy-free module mounted under its own path; the server's `nav` decides what a role sees. */
const FEATURES = { hr: Hr, admin: Admin, supervision: Supervision, monitoring: Monitoring, audit: Audit, mywork: MyWork };

function Protected() {
  const { user } = useAuth();
  return user ? <Layout><Outlet /></Layout> : <Navigate to="/login" replace />;
}

export default function App() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route element={<Protected />}>
        <Route index element={<Navigate to={`/${user?.nav[0]}`} replace />} />
        {user?.nav.map((key) => { const Feature = FEATURES[key]; return <Route key={key} path={`${key}/*`} element={<Feature />} />; })}
        <Route path="roles" element={<Roles />} />
        <Route path="*" element={<div className="card">{t("Page not available for your role.")}</div>} />
      </Route>
    </Routes>
  );
}
