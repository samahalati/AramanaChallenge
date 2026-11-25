import { useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { LangSwitch } from "../../components/Layout";
import Logo from "../../components/Logo";
import { useToast } from "../../components/Toast";
import { isFa, t } from "../../lib/i18n";

const DEMO = [["compliance@aramana.test", "Compliance reviewer"], ["hr@aramana.test", "HR administrator"], ["supervisor1@aramana.test", "Clinical supervisor"],
  ["admin@aramana.test", "Platform admin"], ["admin2@aramana.test", "Platform admin 2 (scenario 4)"], ["therapist1@aramana.test", "Therapist"],
  ["counselor1@aramana.test", "Assistant counselor"], ["hr2@aramana.test", "HR admin 2 (edit burst)"]];

export default function Login() {
  const { login } = useAuth();
  const toast = useToast();
  const [email, setEmail] = useState("compliance@aramana.test");
  const [password, setPassword] = useState("Demo!2345");
  const submit = async (e, as = email) => { e?.preventDefault(); try { await login(as, password); } catch (err) { toast(err.message, true); } };
  return (
    <div className="login card">
      <div className="row between"><Logo /><LangSwitch /></div>
      <h1 style={{ marginTop: 14 }}>{isFa ? "پلتفرم حاکمیت و نظارت آرامانا" : "Aramana governance platform"}</h1>
      <p className="sub">{t("HR administration · clinical supervision · AI-assisted fraud & anomaly detection. Prototype with synthetic data only.")}</p>
      <form onSubmit={submit}>
        <label>{t("E-mail")}</label><input type="email" dir="ltr" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
        <label>{t("Password")}</label><input type="password" dir="ltr" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
        <div className="row" style={{ marginTop: 14 }}><button className="primary" type="submit">{t("Sign in")}</button></div>
      </form>
      <h3>{t("Demo accounts (password Demo!2345)")}</h3>
      <div className="demo">{DEMO.map(([e, label]) => <button key={e} type="button" onClick={() => { setEmail(e); submit(null, e); }}>{t(label)}</button>)}</div>
    </div>
  );
}
