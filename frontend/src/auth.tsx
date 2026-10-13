import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, restore, setAccess, send } from "./api";
import type { AuthInfo } from "./types";
type Auth = {
  info: AuthInfo | null;
  loading: boolean;
  login: (d: unknown, register?: boolean) => Promise<void>;
  logout: () => Promise<void>;
  can: (p: string) => boolean;
};
const Context = createContext<Auth>(null!);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [info, setInfo] = useState<AuthInfo | null>(null),
    [loading, setLoading] = useState(true);
  const qc = useQueryClient();
  useEffect(() => {
    restore()
      .then(setInfo)
      .catch(() => setInfo(null))
      .finally(() => setLoading(false));
  }, []);
  async function login(data: unknown, register = false) {
    const r = await api<{ access_token: string }>(
      register ? "/auth/register" : "/auth/login",
      send(data),
      false,
    );
    setAccess(r.access_token);
    qc.clear();
    setInfo(await api<AuthInfo>("/auth/me"));
  }
  async function logout() {
    try {
      await api("/auth/logout", send({}), false);
    } finally {
      setAccess(null);
      setInfo(null);
      qc.clear();
    }
  }
  return (
    <Context.Provider
      value={{
        info,
        loading,
        login,
        logout,
        can: (p) => !!info?.permissions.includes(p),
      }}
    >
      {children}
    </Context.Provider>
  );
}
export const useAuth = () => useContext(Context);
