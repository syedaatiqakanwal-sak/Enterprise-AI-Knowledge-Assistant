import { api } from "./client";
import type { ApiResponse } from "@/types";

export type AnalyticsRange = "today" | "7d" | "30d" | "90d";

export interface OverviewCards {
  active_users: number;
  documents: number;
  chats: number;
  meetings: number;
  ocr_jobs: number;
  vision_jobs: number;
  agent_tasks: number;
  embeddings: number;
  llm_calls: number;
  api_calls: number;
  errors: number;
  estimated_cost_usd: number;
}

export interface AnalyticsOverview {
  range: string;
  since: string;
  cards: OverviewCards;
  llm: Record<string, number>;
  rag: Record<string, number>;
  agents: Record<string, number>;
  api: Record<string, number>;
  timeline: Array<{ date: string | null; count: number }>;
  top_tools: Array<{ tool: string; count: number }>;
  alerts: Array<{ code: string; severity: string; message: string }>;
  charts: {
    daily_activity: Array<{ date: string | null; count: number }>;
    token_usage: Array<{ name: string; value: number }>;
    top_tools: Array<{ tool: string; count: number }>;
  };
}

export const analyticsApi = {
  overview(range: AnalyticsRange = "30d") {
    return api.get<ApiResponse<AnalyticsOverview>>("/analytics/overview", {
      params: { range },
    });
  },
  users(range: AnalyticsRange = "30d") {
    return api.get<ApiResponse<Record<string, unknown>>>("/analytics/users", {
      params: { range },
    });
  },
  documents(range: AnalyticsRange = "30d") {
    return api.get<ApiResponse<Record<string, unknown>>>("/analytics/documents", {
      params: { range },
    });
  },
  rag(range: AnalyticsRange = "30d") {
    return api.get<ApiResponse<Record<string, unknown>>>("/analytics/rag", {
      params: { range },
    });
  },
  agents(range: AnalyticsRange = "30d") {
    return api.get<ApiResponse<Record<string, unknown>>>("/analytics/agents", {
      params: { range },
    });
  },
  system(range: AnalyticsRange = "30d") {
    return api.get<ApiResponse<Record<string, unknown>>>("/analytics/system", {
      params: { range },
    });
  },
  llm(range: AnalyticsRange = "30d") {
    return api.get<ApiResponse<Record<string, unknown>>>("/analytics/llm", {
      params: { range },
    });
  },
  cost(range: AnalyticsRange = "30d") {
    return api.get<ApiResponse<Record<string, unknown>>>("/analytics/cost", {
      params: { range },
    });
  },
  exportUrl(format: "csv" | "xlsx" | "pdf", range: AnalyticsRange = "30d") {
    return `/analytics/export?format=${format}&range=${range}`;
  },
};
