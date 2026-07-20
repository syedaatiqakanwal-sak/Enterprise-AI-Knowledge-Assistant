import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { authApi, usersApi } from "@/services/api/auth";
import { getErrorMessage, tokenStore } from "@/services/api/client";
import type { User } from "@/types";

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isAdmin: boolean;
  isManager: boolean;
  /** Can enter Admin Portal (admin or manager). */
  isAdminPortal: boolean;
  /** End-user ChatGPT portal (employee without admin/manager). */
  isUserPortal: boolean;
  primaryRole: string | null;
  permissions: string[];
  login: (email: string, password: string) => Promise<User>;
  register: (payload: {
    email: string;
    password: string;
    full_name: string;
    phone?: string;
  }) => Promise<User>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
  /** Post-login home for this user. */
  homePath: string;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function deriveFlags(user: User | null) {
  const roleNames = new Set(user?.roles?.map((r) => r.name) ?? []);
  const isAdmin = roleNames.has("admin") || user?.role === "admin";
  const isManager =
    roleNames.has("manager") ||
    roleNames.has("admin") ||
    user?.role === "manager" ||
    user?.role === "admin";
  const isAdminPortal =
    isAdmin || roleNames.has("manager") || user?.role === "manager";
  const isUserPortal =
    !!user &&
    !isAdminPortal &&
    (roleNames.has("employee") || user?.role === "employee" || roleNames.size === 0);
  const primaryRole =
    user?.role ??
    (isAdmin ? "admin" : roleNames.has("manager") ? "manager" : "employee");
  return {
    isAdmin,
    isManager,
    isAdminPortal,
    isUserPortal,
    primaryRole: user ? primaryRole : null,
    permissions: user?.permissions ?? [],
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshProfile = useCallback(async () => {
    const token = tokenStore.getAccess();
    if (!token) {
      setUser(null);
      return;
    }
    const { data } = await usersApi.me();
    if (data.success && data.data) {
      setUser(data.data);
    } else {
      tokenStore.clear();
      setUser(null);
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        await refreshProfile();
      } catch {
        tokenStore.clear();
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    })();
  }, [refreshProfile]);

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await authApi.login({ email, password });
    if (!data.success || !data.data) {
      throw new Error(data.message || "Login failed");
    }
    tokenStore.set(data.data.tokens.access_token, data.data.tokens.refresh_token);
    setUser(data.data.user);
    return data.data.user;
  }, []);

  const register = useCallback(
    async (payload: {
      email: string;
      password: string;
      full_name: string;
      phone?: string;
    }) => {
      const { data } = await authApi.register(payload);
      if (!data.success || !data.data) {
        throw new Error(data.message || "Registration failed");
      }
      tokenStore.set(
        data.data.tokens.access_token,
        data.data.tokens.refresh_token,
      );
      setUser(data.data.user);
      return data.data.user;
    },
    [],
  );

  const logout = useCallback(async () => {
    const refresh = tokenStore.getRefresh();
    try {
      if (refresh) await authApi.logout(refresh);
    } catch {
      /* ignore */
    } finally {
      tokenStore.clear();
      setUser(null);
    }
  }, []);

  const flags = useMemo(() => deriveFlags(user), [user]);
  const homePath = flags.isAdminPortal ? "/admin" : "/chat";

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: !!user,
      isLoading,
      ...flags,
      login,
      register,
      logout,
      refreshProfile,
      homePath,
    }),
    [user, isLoading, flags, login, register, logout, refreshProfile, homePath],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export { getErrorMessage };
