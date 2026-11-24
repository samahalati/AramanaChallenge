import { useGet } from "../api/hooks";
import { t } from "../lib/i18n";

/** Declarative data loading: <Query path="/hr/dashboard">{(data) => ...}</Query> handles loading + error states once. */
export function Query({ path, children, options }) {
  const { data, error, isLoading } = useGet(path, options);
  if (isLoading) return <p className="muted">{t("Loading…")}</p>;
  if (error) return <div className="card"><h2>{t("Unable to load")}</h2><p>{error.message}</p></div>;
  return children(data);
}

export const Page = ({ title, sub, children }) => <div><h1>{title}</h1>{sub && <p className="sub">{sub}</p>}{children}</div>;
