import { createContext, useContext, useRef, useState } from "react";
import { t } from "../lib/i18n";
import { useToast } from "./Toast";

const FormContext = createContext(() => {});
/** `const ask = useForm(); ask({ title, fields, submit, onSubmit, intro })` opens a modal form driven by a field config. */
export const useForm = () => useContext(FormContext);

function Field({ field, inputRef }) {
  const common = { ref: inputRef, defaultValue: field.value ?? "", placeholder: field.placeholder };
  if (field.type === "select") return <select {...common}>{field.options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>;
  if (field.type === "textarea") return <textarea rows={4} {...common} />;
  if (field.type === "checkbox") return <input type="checkbox" ref={inputRef} defaultChecked={!!field.value} style={{ width: "auto" }} />;
  return <input type={field.type || "text"} {...common} />;
}

const read = (field, el) => (field.type === "checkbox" ? el.checked : field.type === "number" ? (el.value === "" ? null : Number(el.value)) : el.value === "" ? null : el.value);

function Dialog({ config, onClose }) {
  const refs = useRef({});
  const toast = useToast();
  const submit = async (e) => {
    e.preventDefault();
    const values = Object.fromEntries(config.fields.map((f) => [f.name, read(f, refs.current[f.name])]));
    try { await config.onSubmit(values); onClose(); } catch (err) { toast(err.message, true); }
  };
  return (
    <div className="backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="dialog card" onSubmit={submit}>
        <h2>{config.title}</h2>
        {config.intro && <p className="muted small">{config.intro}</p>}
        {config.fields.map((f) => <div key={f.name}><label>{f.label}</label><Field field={f} inputRef={(el) => (refs.current[f.name] = el)} /></div>)}
        <div className="row end"><button type="button" onClick={onClose}>{t("Cancel")}</button><button className="primary" type="submit">{config.submit || t("Submit")}</button></div>
      </form>
    </div>
  );
}

export function FormProvider({ children }) {
  const [config, setConfig] = useState(null);
  return (
    <FormContext.Provider value={setConfig}>
      {children}
      {config && <Dialog config={config} onClose={() => setConfig(null)} />}
    </FormContext.Provider>
  );
}
