import { createContext, useContext, useMemo, useState } from "react";
import { post, session } from "../api/client";

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => session.get()?.user ?? null);
  const value = useMemo(() => ({
    user,
    can: (permission) => !!user?.permissions.includes(permission),
    async login(email, password) {
      const r = await post("/auth/login", { email, password });
      session.set({ token: r.access_token, user: r.user });
      setUser(r.user);
    },
    logout() { session.clear(); setUser(null); },
  }), [user]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
