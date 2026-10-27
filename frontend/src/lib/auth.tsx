"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { api, getToken, setToken, clearToken } from "./api";

type User = { id: string; email: string; full_name: string; timezone: string; niche: string } | null;

const Ctx = createContext<{ user: User; loading: boolean; login: (e: string, p: string) => Promise<void>; signup: (e: string, p: string, n: string) => Promise<void>; logout: () => void }>({
  user: null, loading: true, login: async () => {}, signup: async () => {}, logout: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const t = getToken();
    if (!t) { setLoading(false); return; }
    api.me().then(setUser).catch(() => clearToken()).finally(() => setLoading(false));
  }, []);
  const login = async (email: string, password: string) => {
    const r: any = await api.login(email, password);
    setToken(r.access_token);
    const u = await api.me();
    setUser(u);
  };
  const signup = async (email: string, password: string, name: string) => {
    const r: any = await api.signup(email, password, name);
    setToken(r.access_token);
    const u = await api.me();
    setUser(u);
  };
  const logout = () => { clearToken(); setUser(null); window.location.href = "/"; };
  return <Ctx.Provider value={{ user, loading, login, signup, logout }}>{children}</Ctx.Provider>;
}

export function useAuth() { return useContext(Ctx); }