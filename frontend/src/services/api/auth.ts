import { api } from "./client";
import type { ApiResponse, AuthData, TokenPair, User, UserListData } from "@/types";

export const authApi = {
  register(payload: {
    email: string;
    password: string;
    full_name: string;
    phone?: string;
  }) {
    return api.post<ApiResponse<AuthData>>("/auth/register", payload);
  },
  login(payload: { email: string; password: string }) {
    return api.post<ApiResponse<AuthData>>("/auth/login", payload);
  },
  logout(refresh_token: string) {
    return api.post<ApiResponse<null>>("/auth/logout", { refresh_token });
  },
  refresh(refresh_token: string) {
    return api.post<ApiResponse<TokenPair>>("/auth/refresh", { refresh_token });
  },
  forgotPassword(email: string) {
    return api.post<ApiResponse<null>>("/auth/forgot-password", { email });
  },
  resetPassword(token: string, new_password: string) {
    return api.post<ApiResponse<null>>("/auth/reset-password", {
      token,
      new_password,
    });
  },
  verifyEmail(token: string) {
    return api.post<ApiResponse<null>>("/auth/verify-email", { token });
  },
  changePassword(current_password: string, new_password: string) {
    return api.post<ApiResponse<null>>("/auth/change-password", {
      current_password,
      new_password,
    });
  },
};

export const usersApi = {
  me() {
    return api.get<ApiResponse<User>>("/users/me");
  },
  updateProfile(payload: { full_name?: string; phone?: string | null }) {
    return api.put<ApiResponse<User>>("/users/profile", payload);
  },
  list(params?: { limit?: number; offset?: number }) {
    return api.get<ApiResponse<UserListData>>("/users", { params });
  },
  get(id: string) {
    return api.get<ApiResponse<User>>(`/users/${id}`);
  },
  remove(id: string) {
    return api.delete<ApiResponse<null>>(`/users/${id}`);
  },
};
