import { createContext, useCallback, useContext, useState } from "react";

const ToastContext = createContext(() => {});
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const toast = useCallback((text, error = false) => {
    const id = Math.random();
    setItems((xs) => [...xs, { id, text, error }]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), error ? 6000 : 3000);
  }, []);
  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div id="toasts">{items.map((t) => <div key={t.id} className={`toast ${t.error ? "err" : ""}`}>{t.text}</div>)}</div>
    </ToastContext.Provider>
  );
}
