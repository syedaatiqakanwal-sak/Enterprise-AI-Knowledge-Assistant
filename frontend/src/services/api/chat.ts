import { api } from "./client";
import type { ApiResponse } from "@/types";

export interface Citation {
  document_id: string;
  filename: string;
  page?: number | null;
  chunk_index: number;
  confidence: number;
  snippet: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system" | string;
  content: string;
  citations?: Citation[] | null;
  metrics?: Record<string, number> | null;
  created_at: string;
}

export interface ChatSession {
  id: string;
  title: string;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
  messages?: ChatMessage[];
  preview?: string | null;
}

export interface ChatListData {
  items: ChatSession[];
  total: number;
  limit: number;
  offset: number;
}

export interface ChatAskData {
  chat_id: string;
  user_message: ChatMessage;
  assistant_message: ChatMessage;
  citations: Citation[];
  metrics: Record<string, number>;
}

export const chatApi = {
  ask(payload: {
    message: string;
    chat_id?: string | null;
    folder_id?: string | null;
    document_id?: string | null;
    tag?: string | null;
  }) {
    return api.post<ApiResponse<ChatAskData>>("/chat", payload);
  },
  history(params?: { q?: string; limit?: number; offset?: number }) {
    return api.get<ApiResponse<ChatListData>>("/chat/history", { params });
  },
  get(id: string) {
    return api.get<ApiResponse<ChatSession>>(`/chat/${id}`);
  },
  create(title?: string) {
    return api.post<ApiResponse<ChatSession>>("/chat/sessions", { title });
  },
  update(id: string, payload: { title?: string; is_pinned?: boolean }) {
    return api.patch<ApiResponse<ChatSession>>(`/chat/${id}`, payload);
  },
  remove(id: string) {
    return api.delete<ApiResponse<null>>(`/chat/${id}`);
  },
  search(params: {
    q: string;
    top_k?: number;
    folder_id?: string;
    tag?: string;
  }) {
    return api.get<
      ApiResponse<{
        hits: Citation[];
        metrics: Record<string, number>;
      }>
    >("/search", { params });
  },
};
