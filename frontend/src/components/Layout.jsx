import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { isFa, pretty, setLang, t } from "../lib/i18n";

const TITLES = { hr: "HR & Admin", admin: "Accounts", supervision: "Supervision", monitoring: "Fraud & Anomaly", audit: "Audit", mywork: "My work" };

export const LangSwitch = () => <button type="button" className="lang" onClick={() => setLang(isFa ? "en" : "fa")} title={isFa ? "English" : "فارسی"}>{isFa ? "EN" : "فا"}</button>;

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  return (
    <>
      <header className="top">
        <span className="logo">{isFa ? "آرامنا" : "ARAMANA"}</span>
        <nav>{[...user.nav.map((k) => [k, t(TITLES[k])]), ["roles", t("Roles")]].map(([k, label]) => <NavLink key={k} to={`/${k}`}>{label}</NavLink>)}</nav>
        <LangSwitch />
        <div className="who"><div>{user.full_name}</div><div>{pretty(user.role)} · <a onClick={logout}>{t("sign out")}</a></div></div>
      </header>
      <main>{children}</main>
    </>
  );
}
