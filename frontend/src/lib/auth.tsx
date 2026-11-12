"use client";
import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";

export type Profile = {
  date_of_birth: string | null; gender: string | null; phone: string | null; blood_group: string | null; height_cm: number | null; weight_kg: number | null;
  timezone: string; conditions: string[]; allergies: string[]; food_preference: string; activity_level: string; budget_preference: string;
  doctor_diet_instructions: any[]; emergency_contact_name: string | null; emergency_contact_phone: string | null; onboarding_complete: boolean; large_text: boolean;
};
export type User = { id: string; email: string; full_name: string; role: "patient" | "caregiver"; language: "en" | "hi"; is_demo: boolean; profile?: Profile };

type Ctx = { user: User | null; loading: boolean; refresh: () => Promise<User | null>; logout: () => Promise<void>; setUser: (u: User | null) => void };
const AuthContext = createContext<Ctx>({ user: null, loading: true, refresh: async () => null, logout: async () => {}, setUser: () => {} });

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    try {
      const d = await api<{ user: User }>("/auth/me");
      setUser(d.user);
      return d.user;
    } catch {
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    refresh();
  }, [refresh]);
  useEffect(() => {
    document.documentElement.classList.toggle("large-text", !!user?.profile?.large_text);
  }, [user?.profile?.large_text]);
  const logout = useCallback(async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    setUser(null);
    window.location.href = "/login";
  }, []);
  return <AuthContext.Provider value={{ user, loading, refresh, logout, setUser }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
