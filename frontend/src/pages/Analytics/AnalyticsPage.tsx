import { useCallback, useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Activity,
  AlertTriangle,
  Bot,
  Download,
  FileText,
  MessageSquare,
  Mic,
  ScanText,
  Server,
  Sparkles,
  Users,
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
import { getErrorMessage, api } from "@/services/api/client";
import {
  analyticsApi,
  type AnalyticsOverview,
  type AnalyticsRange,
} from "@/services/api/analytics";
import { cn } from "@/lib/utils";

const RANGES: AnalyticsRange[] = ["today", "7d", "30d", "90d"];
const TABS = [
  "overview",
  "users",
  "documents",
  "rag",
  "agents",
  "system",
  "llm",
  "cost",
] as const;
type Tab = (typeof TABS)[number];

const PIE_COLORS = ["#0ea5e9", "#22c55e", "#f59e0b", "#a855f7", "#ef4444"];

const tooltipStyle = {
  backgroundColor: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: "0.75rem",
};

function StatCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <div className="rounded-lg bg-primary/10 p-2 text-primary">
          <Icon className="h-4 w-4" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-lg font-semibold">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

export function AnalyticsPage() {
  const [range, setRange] = useState<AnalyticsRange>("30d");
  const [tab, setTab] = useState<Tab>("overview");
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [section, setSection] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await analyticsApi.overview(range);
      if (!data.success || !data.data) throw new Error(data.message || "Failed");
      setOverview(data.data);

      if (tab !== "overview") {
        const fn = {
          users: analyticsApi.users,
          documents: analyticsApi.documents,
          rag: analyticsApi.rag,
          agents: analyticsApi.agents,
          system: analyticsApi.system,
          llm: analyticsApi.llm,
          cost: analyticsApi.cost,
        }[tab as Exclude<Tab, "overview">];
        const res = await fn(range);
        if (res.data.success && res.data.data) setSection(res.data.data);
      } else {
        setSection(null);
      }
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to load analytics"));
    } finally {
      setLoading(false);
    }
  }, [range, tab]);

  useEffect(() => {
    void load();
  }, [load]);

  const download = async (format: "csv" | "xlsx" | "pdf") => {
    try {
      const res = await api.get(analyticsApi.exportUrl(format, range), {
        responseType: "blob",
      });
      const blob = new Blob([res.data]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `analytics-${range}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`Exported ${format.toUpperCase()}`);
    } catch (err) {
      toast.error(getErrorMessage(err, "Export failed — need analytics:export"));
    }
  };

  const cards = overview?.cards;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold tracking-tight">
            Analytics & Observability
          </h1>
          <p className="mt-1 text-muted-foreground">
            AI usage, RAG, agents, system health, and cost — production telemetry
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {RANGES.map((r) => (
            <Button
              key={r}
              size="sm"
              variant={range === r ? "default" : "outline"}
              onClick={() => setRange(r)}
            >
              {r}
            </Button>
          ))}
          <Button size="sm" variant="outline" onClick={() => void download("csv")}>
            <Download className="mr-1 h-3.5 w-3.5" />
            CSV
          </Button>
          <Button size="sm" variant="outline" onClick={() => void download("xlsx")}>
            Excel
          </Button>
          <Button size="sm" variant="outline" onClick={() => void download("pdf")}>
            PDF
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-border pb-2">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm capitalize transition",
              tab === t
                ? "bg-primary/15 text-primary"
                : "text-muted-foreground hover:bg-muted"
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {loading && (
        <p className="text-sm text-muted-foreground">Loading telemetry…</p>
      )}

      {cards && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          <StatCard label="Active users" value={cards.active_users} icon={Users} />
          <StatCard label="Documents" value={cards.documents} icon={FileText} />
          <StatCard label="Chats" value={cards.chats} icon={MessageSquare} />
          <StatCard label="Meetings" value={cards.meetings} icon={Mic} />
          <StatCard label="OCR jobs" value={cards.ocr_jobs} icon={ScanText} />
          <StatCard label="Vision jobs" value={cards.vision_jobs} icon={Activity} />
          <StatCard label="Agent tasks" value={cards.agent_tasks} icon={Bot} />
          <StatCard label="LLM calls" value={cards.llm_calls} icon={Sparkles} />
          <StatCard label="API calls" value={cards.api_calls} icon={Server} />
          <StatCard label="Errors" value={cards.errors} icon={AlertTriangle} />
          <StatCard
            label="Est. cost (USD)"
            value={cards.estimated_cost_usd.toFixed(4)}
            icon={Sparkles}
          />
          <StatCard label="Embeddings toks" value={cards.embeddings} icon={Activity} />
        </div>
      )}

      {(overview?.alerts?.length || 0) > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Alerts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {overview!.alerts.map((a) => (
              <div
                key={a.code}
                className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm"
              >
                <span>{a.message}</span>
                <Badge variant={a.severity === "high" ? "warning" : "secondary"}>
                  {a.severity}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {tab === "overview" && overview && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Daily activity</CardTitle>
              <CardDescription>Telemetry events over time</CardDescription>
            </CardHeader>
            <CardContent className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={overview.charts.daily_activity}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Line type="monotone" dataKey="count" stroke="#0ea5e9" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Token mix</CardTitle>
            </CardHeader>
            <CardContent className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={overview.charts.token_usage}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    label
                  >
                    {overview.charts.token_usage.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
          <Card className="lg:col-span-2">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Top tools</CardTitle>
            </CardHeader>
            <CardContent className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={overview.charts.top_tools}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="tool" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar dataKey="count" fill="#22c55e" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>
      )}

      {tab !== "overview" && section && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base capitalize">{tab} metrics</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="max-h-80 overflow-auto rounded-md bg-muted/50 p-3 text-xs">
                {JSON.stringify(section, null, 2)}
              </pre>
            </CardContent>
          </Card>
          {Boolean(
            section &&
              typeof section === "object" &&
              "charts" in section &&
              (section as { charts?: unknown }).charts
          ) && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Charts</CardTitle>
              </CardHeader>
              <CardContent className="h-[320px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={
                      (Object.values(
                        ((section as { charts: Record<string, unknown> }).charts ||
                          {}) as Record<string, unknown>
                      )[0] as Array<Record<string, unknown>> | undefined) || []
                    }
                  >
                    <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Bar dataKey="value" fill="#0ea5e9" radius={[6, 6, 0, 0]} />
                    <Bar dataKey="count" fill="#22c55e" radius={[6, 6, 0, 0]} />
                    <Bar dataKey="cpu" fill="#f59e0b" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
