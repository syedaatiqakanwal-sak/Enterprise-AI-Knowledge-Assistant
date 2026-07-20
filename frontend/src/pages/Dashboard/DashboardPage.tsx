import { Link, useNavigate } from "react-router-dom";
import {
  Activity,
  Bot,
  FileText,
  HardDrive,
  HelpCircle,
  MessageSquare,
  Mic,
  Upload,
  Users,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/common/Card";
import { formatBytes } from "@/lib/utils";

const stats = [
  { label: "Documents", value: "1,284", icon: FileText, change: "+12%" },
  { label: "Meetings", value: "86", icon: Mic, change: "+8%" },
  { label: "Questions", value: "4,521", icon: HelpCircle, change: "+24%" },
  { label: "Storage", value: formatBytes(42_893_568_000), icon: HardDrive, change: "+5%" },
  { label: "AI Responses", value: "9,842", icon: Bot, change: "+18%" },
  { label: "Users", value: "47", icon: Users, change: "+3" },
];

const activityData = [
  { day: "Mon", questions: 120, uploads: 18 },
  { day: "Tue", questions: 145, uploads: 22 },
  { day: "Wed", questions: 98, uploads: 15 },
  { day: "Thu", questions: 167, uploads: 28 },
  { day: "Fri", questions: 134, uploads: 19 },
  { day: "Sat", questions: 45, uploads: 6 },
  { day: "Sun", questions: 38, uploads: 4 },
];

const usageData = [
  { month: "Jan", tokens: 420 },
  { month: "Feb", tokens: 580 },
  { month: "Mar", tokens: 710 },
  { month: "Apr", tokens: 890 },
  { month: "May", tokens: 1020 },
  { month: "Jun", tokens: 1180 },
];

const recentActivity = [
  { action: "Document uploaded", item: "Q2-Financial-Report.pdf", time: "2 min ago" },
  { action: "Chat session", item: "HR policy questions", time: "15 min ago" },
  { action: "Meeting processed", item: "Board-Meeting-Jun.mp4", time: "1 hr ago" },
  { action: "OCR completed", item: "Contract-Scan-001.png", time: "2 hrs ago" },
  { action: "User invited", item: "alex@company.com", time: "3 hrs ago" },
];

const latestDocuments = [
  { name: "Employee-Handbook-2025.pdf", size: "2.4 MB", date: "Today" },
  { name: "Sales-Playbook.docx", size: "890 KB", date: "Yesterday" },
  { name: "Product-Roadmap.xlsx", size: "1.1 MB", date: "Jun 18" },
];

const recentChats = [
  { title: "Remote work policy", messages: 12, time: "10 min ago" },
  { title: "Benefits enrollment", messages: 8, time: "1 hr ago" },
  { title: "Q1 revenue summary", messages: 24, time: "Yesterday" },
];

const systemHealth = [
  { name: "API", status: "Operational", variant: "success" as const },
  { name: "Vector DB", status: "Operational", variant: "success" as const },
  { name: "LLM Gateway", status: "Degraded", variant: "warning" as const },
  { name: "Storage", status: "Operational", variant: "success" as const },
];

export function DashboardPage() {
  const navigate = useNavigate();

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold tracking-tight">
            Dashboard
          </h1>
          <p className="mt-1 text-muted-foreground">
            Overview of your AI knowledge workspace
          </p>
        </div>
        <Button onClick={() => navigate("/documents")}>
          <Upload className="h-4 w-4" />
          Quick upload
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <Card key={stat.label}>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {stat.label}
                </CardTitle>
                <Icon className="h-4 w-4 text-primary" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stat.value}</div>
                <p className="text-xs text-primary">{stat.change} this month</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Weekly activity</CardTitle>
            <CardDescription>Questions asked and documents uploaded</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={activityData}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="day" className="text-xs" tick={{ fill: "hsl(var(--muted-foreground))" }} />
                  <YAxis className="text-xs" tick={{ fill: "hsl(var(--muted-foreground))" }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "0.75rem",
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="questions"
                    stroke="hsl(var(--primary))"
                    fill="hsl(var(--primary))"
                    fillOpacity={0.2}
                  />
                  <Area
                    type="monotone"
                    dataKey="uploads"
                    stroke="hsl(var(--muted-foreground))"
                    fill="hsl(var(--muted-foreground))"
                    fillOpacity={0.1}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Token usage</CardTitle>
            <CardDescription>Monthly AI consumption trend</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={usageData}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="month" tick={{ fill: "hsl(var(--muted-foreground))" }} />
                  <YAxis tick={{ fill: "hsl(var(--muted-foreground))" }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "0.75rem",
                    }}
                  />
                  <Bar dataKey="tokens" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-primary" />
              Recent activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-4">
              {recentActivity.map((item) => (
                <li key={item.item} className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-medium">{item.action}</p>
                    <p className="text-xs text-muted-foreground">{item.item}</p>
                  </div>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {item.time}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-primary" />
              Latest documents
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {latestDocuments.map((doc) => (
                <li
                  key={doc.name}
                  className="flex items-center justify-between rounded-lg border border-border/60 px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{doc.name}</p>
                    <p className="text-xs text-muted-foreground">{doc.size}</p>
                  </div>
                  <span className="text-xs text-muted-foreground">{doc.date}</span>
                </li>
              ))}
            </ul>
            <Button asChild variant="ghost" className="mt-4 w-full" size="sm">
              <Link to="/admin/documents">View all documents</Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-primary" />
              Recent chats
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {recentChats.map((chat) => (
                <li
                  key={chat.title}
                  className="flex items-center justify-between rounded-lg border border-border/60 px-3 py-2"
                >
                  <div>
                    <p className="text-sm font-medium">{chat.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {chat.messages} messages
                    </p>
                  </div>
                  <span className="text-xs text-muted-foreground">{chat.time}</span>
                </li>
              ))}
            </ul>
            <Button asChild variant="ghost" className="mt-4 w-full" size="sm">
              <Link to="/admin/documents">Open documents</Link>
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>System health</CardTitle>
          <CardDescription>Real-time service status</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            {systemHealth.map((service) => (
              <div
                key={service.name}
                className="flex items-center gap-2 rounded-lg border border-border px-4 py-2"
              >
                <span className="text-sm font-medium">{service.name}</span>
                <Badge variant={service.variant}>{service.status}</Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
