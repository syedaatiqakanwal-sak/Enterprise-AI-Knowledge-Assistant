import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bot,
  CheckCircle2,
  Circle,
  GitBranch,
  History,
  Play,
  Plus,
  Trash2,
  Wrench,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/common/Card";
import { getErrorMessage } from "@/services/api/client";
import {
  agentApi,
  type AgentRunResult,
  type AgentSessionItem,
  type AgentTaskItem,
  type RegisteredTool,
  type ToolExecution,
  type WorkflowItem,
} from "@/services/api/agent";
import { cn } from "@/lib/utils";

const AGENT_TYPES = [
  "general_assistant",
  "knowledge",
  "document",
  "meeting",
  "ocr",
  "vision",
  "sql",
  "email",
  "calendar",
];

const NODE_TYPES = ["llm", "tool", "condition", "loop", "output"] as const;

type ChatBubble = { role: "user" | "assistant"; content: string };

export function AgentsPage() {
  const [agentType, setAgentType] = useState("general_assistant");
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);
  const [chat, setChat] = useState<ChatBubble[]>([]);
  const [lastRun, setLastRun] = useState<AgentRunResult | null>(null);
  const [history, setHistory] = useState<AgentSessionItem[]>([]);
  const [tasks, setTasks] = useState<AgentTaskItem[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [tools, setTools] = useState<RegisteredTool[]>([]);
  const [wfName, setWfName] = useState("Meeting summary pipeline");
  const [builderNodes, setBuilderNodes] = useState<
    Array<{ id: string; type: string; label: string; tool?: string }>
  >([
    { id: "n1", type: "tool", label: "Search meeting", tool: "meeting_search" },
    { id: "n2", type: "tool", label: "Summarize", tool: "meeting_summarizer" },
    { id: "n3", type: "output", label: "Done" },
  ]);

  const refresh = useCallback(async () => {
    const [h, t, w, tl] = await Promise.all([
      agentApi.history({ limit: 20 }),
      agentApi.tasks({ limit: 20 }),
      agentApi.workflows({ limit: 20 }),
      agentApi.tools(agentType),
    ]);
    if (h.data.success && h.data.data) setHistory(h.data.data.items);
    if (t.data.success && t.data.data) setTasks(t.data.data.items);
    if (w.data.success && w.data.data) setWorkflows(w.data.data.items);
    if (tl.data.success && tl.data.data) setTools(tl.data.data.tools);
  }, [agentType]);

  useEffect(() => {
    void refresh().catch((err) =>
      toast.error(getErrorMessage(err, "Failed to load agent data"))
    );
  }, [refresh]);

  const send = async (confirm = false) => {
    const message = input.trim();
    if (!message && !confirm) return;
    const text = confirm
      ? lastRun
        ? `Confirm: ${lastRun.plan.goal || "previous action"}`
        : message
      : message;
    if (!confirm) {
      setChat((c) => [...c, { role: "user", content: text }]);
      setInput("");
    }
    setBusy(true);
    try {
      const { data } = await agentApi.chat({
        message: confirm && lastRun ? lastRun.plan.goal || text : text,
        session_id: sessionId,
        agent_type: agentType,
        confirm,
      });
      if (!data.success || !data.data) throw new Error(data.message || "Agent failed");
      const run = data.data;
      setSessionId(run.session_id);
      setLastRun(run);
      setChat((c) => [...c, { role: "assistant", content: run.answer }]);
      if (run.waiting_confirmation) {
        toast.message("Confirmation required before email/tool side-effect");
      } else {
        toast.success("Agent completed");
      }
      await refresh();
    } catch (err) {
      toast.error(getErrorMessage(err, "Agent run failed"));
    } finally {
      setBusy(false);
    }
  };

  const createWorkflow = async () => {
    try {
      const steps = builderNodes.map((n, i) => ({
        node_id: n.id,
        node_type: n.type,
        label: n.label,
        position: i,
        config:
          n.type === "tool"
            ? { tool: n.tool || "current_time", args: {} }
            : n.type === "output"
              ? { message: "Workflow complete" }
              : {},
        next_on_success: builderNodes[i + 1]?.id || "end",
        next_on_failure: "end",
      }));
      const { data } = await agentApi.createWorkflow({
        name: wfName,
        description: "Created from visual builder",
        status: "active",
        steps,
        graph: {
          entry: builderNodes[0]?.id,
          nodes: steps.map((s) => ({
            id: s.node_id,
            type: s.node_type,
            label: s.label,
            config: s.config,
            next_on_success: s.next_on_success,
            next_on_failure: s.next_on_failure,
          })),
        },
      });
      if (!data.success) throw new Error(data.message || "Create failed");
      toast.success("Workflow saved");
      await refresh();
    } catch (err) {
      toast.error(getErrorMessage(err, "Workflow create failed"));
    }
  };

  const addBuilderNode = (type: string) => {
    const id = `n${builderNodes.length + 1}`;
    setBuilderNodes((nodes) => [
      ...nodes,
      {
        id,
        type,
        label: type === "tool" ? "Tool step" : type,
        tool: type === "tool" ? "rag_search" : undefined,
      },
    ]);
  };

  const executions: ToolExecution[] = useMemo(
    () => lastRun?.tool_executions || [],
    [lastRun]
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl font-bold tracking-tight">
          AI Agent Platform
        </h1>
        <p className="mt-1 text-muted-foreground">
          Plan → select tools → execute → remember. Plugin tool registry, not a chatbot.
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Bot className="h-4 w-4 text-primary" />
                  Agent chat
                </CardTitle>
                <select
                  value={agentType}
                  onChange={(e) => setAgentType(e.target.value)}
                  className="h-9 rounded-md border border-border bg-background px-3 text-sm"
                >
                  {AGENT_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
              <CardDescription>
                Try: “Summarize yesterday&apos;s meeting and email it to my manager.”
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="max-h-72 space-y-2 overflow-y-auto rounded-lg border border-border p-3">
                {chat.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    Ask the agent to plan multi-step work across knowledge, meetings, OCR, and more.
                  </p>
                )}
                {chat.map((m, i) => (
                  <div
                    key={i}
                    className={cn(
                      "rounded-md px-3 py-2 text-sm",
                      m.role === "user" ? "bg-primary/10" : "bg-muted/60"
                    )}
                  >
                    <span className="mr-2 text-xs font-semibold uppercase text-muted-foreground">
                      {m.role}
                    </span>
                    {m.content}
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap gap-2">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && void send(false)}
                  placeholder="Describe a multi-step goal…"
                  className="h-10 min-w-[200px] flex-1 rounded-md border border-border bg-background px-3 text-sm"
                  disabled={busy}
                />
                <Button onClick={() => void send(false)} disabled={busy}>
                  <Play className="mr-1 h-4 w-4" />
                  Run
                </Button>
                {lastRun?.waiting_confirmation && (
                  <Button variant="outline" onClick={() => void send(true)} disabled={busy}>
                    Confirm action
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Execution timeline</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {(lastRun?.reasoning || []).map((r, i) => (
                  <div key={i} className="flex gap-2 text-sm">
                    <Circle className="mt-1 h-3 w-3 shrink-0 text-primary" />
                    <span>{r}</span>
                  </div>
                ))}
                {!lastRun && (
                  <p className="text-sm text-muted-foreground">No run yet</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Wrench className="h-4 w-4" />
                  Tool usage
                </CardTitle>
              </CardHeader>
              <CardContent className="max-h-64 space-y-2 overflow-y-auto">
                {executions.length === 0 && (
                  <p className="text-sm text-muted-foreground">No tool calls</p>
                )}
                {executions.map((e, i) => (
                  <div
                    key={e.id || i}
                    className="rounded-lg border border-border p-3 text-sm"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{e.tool_name}</span>
                      <Badge
                        variant={
                          e.status === "success"
                            ? "success"
                            : e.status === "failed"
                              ? "warning"
                              : "secondary"
                        }
                      >
                        {e.status}
                      </Badge>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {e.latency_ms ?? 0} ms · retries {e.retries ?? 0}
                    </p>
                    {e.error && (
                      <p className="mt-1 text-xs text-destructive">{e.error}</p>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <GitBranch className="h-4 w-4" />
                Workflow builder
              </CardTitle>
              <CardDescription>
                Drag-ready node types: LLM, Tool, Condition, Loop, Output
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {NODE_TYPES.map((t) => (
                  <Button
                    key={t}
                    size="sm"
                    variant="outline"
                    onClick={() => addBuilderNode(t)}
                  >
                    <Plus className="mr-1 h-3 w-3" />
                    {t}
                  </Button>
                ))}
              </div>
              <input
                value={wfName}
                onChange={(e) => setWfName(e.target.value)}
                className="h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
              />
              <div className="flex flex-wrap gap-3">
                {builderNodes.map((n, idx) => (
                  <div
                    key={n.id}
                    className="min-w-[140px] rounded-lg border border-border bg-muted/40 p-3 text-sm"
                  >
                    <p className="text-xs uppercase text-muted-foreground">{n.type}</p>
                    <p className="font-medium">{n.label}</p>
                    {n.tool && (
                      <p className="text-xs text-muted-foreground">{n.tool}</p>
                    )}
                    {idx < builderNodes.length - 1 && (
                      <p className="mt-2 text-xs text-primary">→ {builderNodes[idx + 1].id}</p>
                    )}
                  </div>
                ))}
              </div>
              <Button onClick={() => void createWorkflow()}>Save workflow</Button>
              {workflows.length > 0 && (
                <div className="space-y-2 pt-2">
                  {workflows.map((w) => (
                    <div
                      key={w.id}
                      className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm"
                    >
                      <span>{w.name}</span>
                      <Badge variant="secondary">{w.status}</Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Memory panel</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="max-h-40 overflow-auto rounded-md bg-muted/50 p-3 text-xs">
                {JSON.stringify(lastRun?.memory || {}, null, 2)}
              </pre>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <History className="h-4 w-4" />
                Task history
              </CardTitle>
            </CardHeader>
            <CardContent className="max-h-56 space-y-2 overflow-y-auto">
              {tasks.map((t) => (
                <div
                  key={t.id}
                  className="rounded-lg border border-border p-3 text-sm"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="line-clamp-2 font-medium">{t.goal}</p>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={async () => {
                        await agentApi.deleteTask(t.id);
                        toast.success("Task deleted");
                        await refresh();
                      }}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <Badge variant="secondary">{t.status}</Badge>
                    {(t.tool_executions?.length || 0) > 0 && (
                      <span className="text-xs text-muted-foreground">
                        {t.tool_executions!.length} tools
                      </span>
                    )}
                  </div>
                </div>
              ))}
              {tasks.length === 0 && (
                <p className="text-sm text-muted-foreground">No tasks yet</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Sessions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {history.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className={cn(
                    "flex w-full items-center justify-between rounded-md border border-transparent px-2 py-2 text-left text-sm hover:bg-muted/60",
                    sessionId === s.id && "border-border bg-muted/80"
                  )}
                  onClick={() => setSessionId(s.id)}
                >
                  <span className="truncate">{s.title}</span>
                  {sessionId === s.id && (
                    <CheckCircle2 className="h-3.5 w-3.5 text-primary" />
                  )}
                </button>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Plugin tools</CardTitle>
              <CardDescription>{tools.length} registered</CardDescription>
            </CardHeader>
            <CardContent className="max-h-48 space-y-1 overflow-y-auto text-xs">
              {tools.map((t) => (
                <div key={t.name} className="rounded border border-border/60 px-2 py-1.5">
                  <p className="font-medium">{t.name}</p>
                  <p className="text-muted-foreground line-clamp-2">{t.description}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
