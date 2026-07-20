import { api } from "./client";
import type { ApiResponse } from "@/types";

export interface ToolExecution {
  id?: string;
  tool_name: string;
  step_index: number;
  status: string;
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  error?: string | null;
  latency_ms?: number;
  retries?: number;
}

export interface AgentRunResult {
  session_id: string;
  task_id: string;
  agent_type: string;
  answer: string;
  plan: {
    goal?: string;
    steps?: Array<{ tool: string; args?: Record<string, unknown>; rationale?: string }>;
    reasoning?: string[];
    required_tools?: string[];
  };
  reasoning: string[];
  tool_executions: ToolExecution[];
  waiting_confirmation: boolean;
  confirmation_action?: string | null;
  metrics: Record<string, unknown>;
  status: string;
  memory?: Record<string, unknown>;
}

export interface AgentSessionItem {
  id: string;
  title: string;
  agent_type: string;
  status: string;
  created_at?: string | null;
  message_count?: number;
}

export interface AgentTaskItem {
  id: string;
  session_id: string;
  goal: string;
  status: string;
  plan?: Record<string, unknown>;
  reasoning_steps?: string[];
  tool_executions?: ToolExecution[];
  metrics?: Record<string, unknown>;
  created_at?: string | null;
}

export interface WorkflowItem {
  id: string;
  name: string;
  description?: string | null;
  status: string;
  graph?: {
    entry?: string | null;
    nodes?: Array<{
      id: string;
      type: string;
      label?: string;
      config?: Record<string, unknown>;
      next_on_success?: string | null;
      next_on_failure?: string | null;
    }>;
  };
  steps?: Array<{
    id: string;
    node_id: string;
    node_type: string;
    label: string;
    position: number;
    config?: Record<string, unknown>;
  }>;
  created_at?: string | null;
}

export interface RegisteredTool {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  tags?: string[];
}

export const agentApi = {
  chat(payload: {
    message: string;
    session_id?: string;
    agent_type?: string;
    confirm?: boolean;
  }) {
    return api.post<ApiResponse<AgentRunResult>>("/agent/chat", payload);
  },
  run(payload: {
    goal: string;
    session_id?: string;
    agent_type?: string;
    confirm?: boolean;
    workflow_id?: string;
  }) {
    return api.post<ApiResponse<AgentRunResult>>("/agent/run", payload);
  },
  history(params?: { limit?: number }) {
    return api.get<
      ApiResponse<{ items: AgentSessionItem[]; total: number }>
    >("/agent/history", { params });
  },
  tasks(params?: { limit?: number }) {
    return api.get<ApiResponse<{ items: AgentTaskItem[]; total: number }>>(
      "/agent/tasks",
      { params }
    );
  },
  deleteTask(id: string) {
    return api.delete<ApiResponse<{ id: string }>>(`/agent/tasks/${id}`);
  },
  workflows(params?: { limit?: number }) {
    return api.get<ApiResponse<{ items: WorkflowItem[]; total: number }>>(
      "/agent/workflows",
      { params }
    );
  },
  createWorkflow(payload: {
    name: string;
    description?: string;
    status?: string;
    graph?: WorkflowItem["graph"];
    steps?: Array<Record<string, unknown>>;
  }) {
    return api.post<ApiResponse<WorkflowItem>>("/agent/workflows", payload);
  },
  tools(agentType?: string) {
    return api.get<ApiResponse<{ tools: RegisteredTool[] }>>("/agent/tools", {
      params: agentType ? { agent_type: agentType } : undefined,
    });
  },
};
