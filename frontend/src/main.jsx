import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { FormProvider } from "./components/FormModal";
import { ToastProvider } from "./components/Toast";
import { loadLabels } from "./lib/i18n";
import "./styles.css";

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false, staleTime: 5_000 } } });

await loadLabels();   // server vocabulary (enums, roles, evidence keys) must be ready before any feature module is evaluated
const { default: App } = await import("./App");
createRoot(document.getElementById("root")).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ToastProvider><FormProvider><AuthProvider><BrowserRouter><App /></BrowserRouter></AuthProvider></FormProvider></ToastProvider>
    </QueryClientProvider>
  </StrictMode>,
);
