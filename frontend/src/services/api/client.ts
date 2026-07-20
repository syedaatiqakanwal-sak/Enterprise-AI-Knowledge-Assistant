import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

/**
 * In Vite dev, prefer same-origin `/api` (proxied to backend) to avoid CORS.
 * Set VITE_API_URL to an absolute URL only when calling the API directly.
 */
const configured = (import.meta.env.VITE_API_URL as string | undefined)?.trim();
const API_ORIGIN = configured && configured.length > 0 ? configured.replace(/\/$/, "") : "";

export const api = axios.create({
  baseURL: API_ORIGIN ? `${API_ORIGIN}/api/v1` : "/api/v1",
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
});

const ACCESS_KEY = "eai_access_token";
const REFRESH_KEY = "eai_refresh_token";

export const tokenStore = {
  getAccess: () => localStorage.getItem(ACCESS_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set(access: string, refresh: string) {
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = tokenStore.getAccess();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshing: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh = tokenStore.getRefresh();
  if (!refresh) return null;
  try {
    const refreshUrl = API_ORIGIN
      ? `${API_ORIGIN}/api/v1/auth/refresh`
      : "/api/v1/auth/refresh";
    const { data } = await axios.post(refreshUrl, {
      refresh_token: refresh,
    });
    if (data?.success && data?.data) {
      tokenStore.set(data.data.access_token, data.data.refresh_token);
      return data.data.access_token as string;
    }
  } catch {
    tokenStore.clear();
  }
  return null;
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };
    if (error.response?.status === 401 && original && !original._retry) {
      original._retry = true;
      refreshing = refreshing ?? refreshAccessToken();
      const newToken = await refreshing;
      refreshing = null;
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      }
    }
    return Promise.reject(error);
  },
);

export function getErrorMessage(error: unknown, fallback?: string): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | { message?: string; errors?: unknown }
      | undefined;
    if (data?.message) return data.message;
    if (error.message === "Network Error") {
      return "Cannot reach the API. Is the backend running on port 8000?";
    }
    return error.message || fallback || "Request failed";
  }
  if (error instanceof Error) return error.message || fallback || "Unexpected error";
  return fallback || "Unexpected error";
}
