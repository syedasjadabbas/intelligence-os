"use client";

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react";
import { useRouter, usePathname } from "next/navigation";
import {
  api,
  User,
  Organization,
  LoginPayload,
  RegisterOrgPayload,
} from "@/lib/api";

interface AuthContextType {
  user: User | null;
  org: Organization | null;
  token: string | null;
  loading: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterOrgPayload) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [org, setOrg] = useState<Organization | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const router = useRouter();
  const pathname = usePathname();

  const refreshUser = useCallback(async () => {
    const existingToken = api.getToken();
    if (!existingToken) {
      setUser(null);
      setOrg(null);
      setTokenState(null);
      setLoading(false);
      return;
    }

    try {
      setTokenState(existingToken);
      const userData = await api.getMe();
      // Ensure the token has not changed while getMe was resolving
      if (api.getToken() === existingToken) {
        if (userData && typeof userData === "object") {
          setUser(userData);
          if (userData.organization) {
            setOrg(userData.organization);
          }
        } else {
          throw new Error("Invalid user response format");
        }
      }
    } catch (err: any) {
      console.warn("Auth token validation failed or backend offline:", err.message || err);
      // Only clear credentials if definitely an authentication rejection and token was not superseded
      if (api.getToken() === existingToken) {
        const isAuthRejection =
          err?.message &&
          (err.message.includes("401") ||
           err.message.includes("Could not validate credentials") ||
           err.message.includes("Not authenticated"));
        if (isAuthRejection) {
          api.clearToken();
          setUser(null);
          setOrg(null);
          setTokenState(null);
        }
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Safety fallback: ensure loading state never permanently blocks or deadlocks the UI
    const safetyTimer = setTimeout(() => {
      setLoading(false);
    }, 1500);

    refreshUser().finally(() => {
      clearTimeout(safetyTimer);
      setLoading(false);
    });

    return () => clearTimeout(safetyTimer);
  }, [refreshUser]);

  // Protected route guard
  useEffect(() => {
    if (loading) return;

    const isAuthPage =
      pathname === "/login" || pathname === "/register";

    if (!user && !isAuthPage) {
      // If token exists in local storage, allow page to render while background sync resolves
      const existingToken = api.getToken();
      if (!existingToken) {
        router.replace("/login");
      }
    } else if (user && isAuthPage) {
      router.replace("/");
    }
  }, [user, loading, pathname, router]);

  const login = async (payload: LoginPayload) => {
    try {
      const res = await api.login(payload);
      setUser(res.user);
      setOrg(res.organization);
      setTokenState(res.access_token);
      setLoading(false);
      router.push("/");
    } finally {
      setLoading(false);
    }
  };

  const register = async (payload: RegisterOrgPayload) => {
    try {
      const res = await api.registerOrg(payload);
      setUser(res.user);
      setOrg(res.organization);
      setTokenState(res.access_token);
      setLoading(false);
      router.push("/");
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    api.clearToken();
    setUser(null);
    setOrg(null);
    setTokenState(null);
    router.replace("/login");
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        org,
        token,
        loading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
