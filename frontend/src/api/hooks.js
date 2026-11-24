import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToast } from "../components/Toast";
import { get } from "./client";

/** GET with caching. `useGet(path)` -> react-query result. */
export const useGet = (path, options = {}) => useQuery({ queryKey: [path], queryFn: () => get(path), ...options });

/** Mutation runner: `const act = useAct(); await act(() => post(...), "Saved")` – toasts the outcome and refreshes every query. */
export function useAct() {
  const qc = useQueryClient();
  const toast = useToast();
  return async (fn, success) => {
    try {
      const result = await fn();
      if (success) toast(typeof success === "function" ? success(result) : success);
      await qc.invalidateQueries();
      return result;
    } catch (e) {
      toast(e.message, true);
    }
  };
}
