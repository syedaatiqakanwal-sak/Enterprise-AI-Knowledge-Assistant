import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import {
  AlertTriangle,
  Bell,
  Building2,
  Cpu,
  Globe,
  Loader2,
  Lock,
  Moon,
  Palette,
  Sun,
  User,
} from "lucide-react";
import { authApi } from "@/services/api/auth";
import { usersApi } from "@/services/api/auth";
import { getErrorMessage } from "@/services/api/client";
import { systemApi, type OllamaStatus } from "@/services/api/system";
import { useAuth, getErrorMessage as authErrorMessage } from "@/contexts/AuthContext";
import { useTheme } from "@/contexts/ThemeContext";
import type { ThemeMode } from "@/types";
import { Button } from "@/components/common/Button";
import { Input } from "@/components/common/Input";
import { Label } from "@/components/common/Label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/common/Card";
import { Badge } from "@/components/common/Badge";
import { cn } from "@/lib/utils";

const tabs = [
  { id: "profile", label: "Profile", icon: User },
  { id: "company", label: "Company", icon: Building2 },
  { id: "ai", label: "AI / Ollama", icon: Cpu },
  { id: "password", label: "Password", icon: Lock },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "theme", label: "Theme", icon: Palette },
  { id: "language", label: "Language", icon: Globe },
  { id: "danger", label: "Danger Zone", icon: AlertTriangle },
] as const;

type TabId = (typeof tabs)[number]["id"];

const passwordPattern =
  /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,128}$/;

const profileSchema = z.object({
  full_name: z.string().min(2, "Name must be at least 2 characters"),
  phone: z.string().optional(),
});

const passwordSchema = z
  .object({
    current_password: z.string().min(1, "Current password is required"),
    new_password: z
      .string()
      .regex(
        passwordPattern,
        "Password must be 8–128 characters and include uppercase, lowercase, digit, and special character"
      ),
    confirm_password: z.string(),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type ProfileForm = z.infer<typeof profileSchema>;
type PasswordForm = z.infer<typeof passwordSchema>;

export function SettingsPage() {
  const { user, refreshProfile } = useAuth();
  const { theme, setTheme, resolved } = useTheme();
  const [activeTab, setActiveTab] = useState<TabId>("profile");
  const [profileSaving, setProfileSaving] = useState(false);
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [ollamaStatus, setOllamaStatus] = useState<OllamaStatus | null>(null);
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [ollamaLoading, setOllamaLoading] = useState(false);
  const [ollamaTesting, setOllamaTesting] = useState(false);
  const [llmProvider, setLlmProvider] = useState<string>("");
  const [embeddingProvider, setEmbeddingProvider] = useState<string>("");

  const loadOllamaPanel = async () => {
    setOllamaLoading(true);
    try {
      const [statusRes, modelsRes, llmRes] = await Promise.all([
        systemApi.ollamaStatus(),
        systemApi.ollamaModels(),
        systemApi.llmInfo(),
      ]);
      if (statusRes.data.success && statusRes.data.data) {
        setOllamaStatus(statusRes.data.data);
        setLlmProvider(
          statusRes.data.data.llm_provider_setting ||
            llmRes.data.data?.provider ||
            "",
        );
        setEmbeddingProvider(statusRes.data.data.embedding_provider || "");
      }
      if (modelsRes.data.success && modelsRes.data.data) {
        setOllamaModels(modelsRes.data.data.models || []);
        const sel =
          modelsRes.data.data.selected_model ||
          statusRes.data.data?.selected_model ||
          "";
        setSelectedModel(sel || "");
      }
      if (llmRes.data.success && llmRes.data.data) {
        setLlmProvider(llmRes.data.data.llm_provider_setting);
        setEmbeddingProvider(llmRes.data.data.embedding_provider);
      }
    } catch (error) {
      toast.error(getErrorMessage(error) || "Failed to load Ollama status");
    } finally {
      setOllamaLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === "ai") {
      void loadOllamaPanel();
    }
  }, [activeTab]);

  const onTestOllama = async () => {
    setOllamaTesting(true);
    try {
      const { data } = await systemApi.testOllama(selectedModel || null);
      if (data.data) setOllamaStatus(data.data);
      if (data.success && data.data?.reachable && !data.data.error) {
        toast.success(data.message || "Ollama connection OK");
      } else {
        toast.error(data.data?.error || data.message || "Ollama test failed");
      }
    } catch (error) {
      toast.error(getErrorMessage(error) || "Ollama test failed");
    } finally {
      setOllamaTesting(false);
    }
  };

  const onSelectModel = async () => {
    if (!selectedModel) {
      toast.error("Select a model first");
      return;
    }
    try {
      const { data } = await systemApi.selectOllamaModel(selectedModel);
      if (!data.success) {
        throw new Error(data.message || "Failed to select model");
      }
      toast.success(data.message || `Model set to ${selectedModel}`);
      await loadOllamaPanel();
    } catch (error) {
      toast.error(getErrorMessage(error) || "Failed to select model");
    }
  };

  const profileForm = useForm<ProfileForm>({
    resolver: zodResolver(profileSchema),
    values: {
      full_name: user?.full_name ?? "",
      phone: user?.phone ?? "",
    },
  });

  const passwordForm = useForm<PasswordForm>({
    resolver: zodResolver(passwordSchema),
    defaultValues: {
      current_password: "",
      new_password: "",
      confirm_password: "",
    },
  });

  const onProfileSubmit = async (data: ProfileForm) => {
    setProfileSaving(true);
    try {
      const { data: response } = await usersApi.updateProfile({
        full_name: data.full_name,
        phone: data.phone || null,
      });
      if (!response.success) {
        throw new Error(response.message || "Update failed");
      }
      await refreshProfile();
      toast.success("Profile updated");
    } catch (error) {
      toast.error(authErrorMessage(error));
    } finally {
      setProfileSaving(false);
    }
  };

  const onPasswordSubmit = async (data: PasswordForm) => {
    setPasswordSaving(true);
    try {
      const { data: response } = await authApi.changePassword(
        data.current_password,
        data.new_password
      );
      if (!response.success) {
        throw new Error(response.message || "Password change failed");
      }
      passwordForm.reset();
      toast.success("Password changed successfully");
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setPasswordSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl font-bold tracking-tight">
          Settings
        </h1>
        <p className="mt-1 text-muted-foreground">
          Manage your account and preferences
        </p>
      </div>

      <div className="flex flex-col gap-6 lg:flex-row">
        <nav className="flex shrink-0 gap-2 overflow-x-auto lg:w-56 lg:flex-col">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium whitespace-nowrap transition-colors",
                  activeTab === tab.id
                    ? "bg-primary/15 text-primary"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground",
                  tab.id === "danger" &&
                    activeTab !== "danger" &&
                    "text-destructive/80"
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {tab.label}
              </button>
            );
          })}
        </nav>

        <div className="min-w-0 flex-1">
          {activeTab === "profile" && (
            <Card>
              <CardHeader>
                <CardTitle>Profile</CardTitle>
                <CardDescription>Update your personal information</CardDescription>
              </CardHeader>
              <CardContent>
                <form
                  onSubmit={profileForm.handleSubmit(onProfileSubmit)}
                  className="max-w-md space-y-4"
                >
                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <Input
                      id="email"
                      value={user?.email ?? ""}
                      disabled
                      className="bg-muted/50"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="full_name">Full name</Label>
                    <Input
                      id="full_name"
                      {...profileForm.register("full_name")}
                    />
                    {profileForm.formState.errors.full_name && (
                      <p className="text-sm text-destructive">
                        {profileForm.formState.errors.full_name.message}
                      </p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="phone">Phone</Label>
                    <Input id="phone" {...profileForm.register("phone")} />
                  </div>
                  <Button type="submit" disabled={profileSaving}>
                    {profileSaving && <Loader2 className="animate-spin" />}
                    Save changes
                  </Button>
                </form>
              </CardContent>
            </Card>
          )}

          {activeTab === "company" && (
            <Card>
              <CardHeader>
                <CardTitle>Company</CardTitle>
                <CardDescription>Organization settings (UI preview)</CardDescription>
              </CardHeader>
              <CardContent className="max-w-md space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="company">Company name</Label>
                  <Input id="company" defaultValue="Acme Corporation" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="industry">Industry</Label>
                  <select
                    id="industry"
                    className="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                    defaultValue="Technology"
                  >
                    <option>Technology</option>
                    <option>Finance</option>
                    <option>Healthcare</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="domain">Domain</Label>
                  <Input id="domain" defaultValue="acme.com" />
                </div>
                <Button disabled>Save company settings</Button>
              </CardContent>
            </Card>
          )}

          {activeTab === "ai" && (
            <Card>
              <CardHeader>
                <CardTitle>AI / Ollama</CardTitle>
                <CardDescription>
                  Current LLM provider, embedding provider, and local Ollama
                  connection status
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">
                    LLM: {llmProvider || "—"}
                  </Badge>
                  <Badge variant="secondary">
                    Embeddings: {embeddingProvider || "—"}
                  </Badge>
                  <Badge variant="secondary">
                    Model: {ollamaStatus?.selected_model || selectedModel || "—"}
                  </Badge>
                  <Badge
                    variant={
                      ollamaStatus?.reachable ? "success" : "warning"
                    }
                  >
                    Ollama:{" "}
                    {ollamaLoading
                      ? "checking…"
                      : ollamaStatus?.reachable
                        ? "reachable"
                        : "unreachable"}
                  </Badge>
                </div>

                <div className="grid gap-3 text-sm sm:grid-cols-2">
                  <div className="rounded-lg border border-border p-3">
                    <p className="text-muted-foreground">Version</p>
                    <p className="font-medium">
                      {ollamaStatus?.version ?? "—"}
                    </p>
                  </div>
                  <div className="rounded-lg border border-border p-3">
                    <p className="text-muted-foreground">Latency</p>
                    <p className="font-medium">
                      {ollamaStatus?.latency_ms != null
                        ? `${ollamaStatus.latency_ms} ms`
                        : "—"}
                    </p>
                  </div>
                  <div className="rounded-lg border border-border p-3">
                    <p className="text-muted-foreground">GPU</p>
                    <p className="font-medium">
                      {ollamaStatus?.gpu_available == null
                        ? "unknown"
                        : ollamaStatus.gpu_available
                          ? "available"
                          : "not detected"}
                    </p>
                  </div>
                  <div className="rounded-lg border border-border p-3">
                    <p className="text-muted-foreground">Base URL</p>
                    <p className="font-medium break-all">
                      {ollamaStatus?.base_url ?? "—"}
                    </p>
                  </div>
                </div>

                {ollamaStatus?.error ? (
                  <p className="text-sm text-destructive">{ollamaStatus.error}</p>
                ) : null}

                <div className="max-w-md space-y-2">
                  <Label htmlFor="ollama-model">Ollama model</Label>
                  <select
                    id="ollama-model"
                    className="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    disabled={ollamaLoading || ollamaModels.length === 0}
                  >
                    {ollamaModels.length === 0 ? (
                      <option value="">No models discovered</option>
                    ) : (
                      ollamaModels.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))
                    )}
                  </select>
                  <p className="text-xs text-muted-foreground">
                    Models are discovered from the local Ollama server. Pull new
                    ones with <code>ollama pull &lt;name&gt;</code>.
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => void loadOllamaPanel()}
                    disabled={ollamaLoading}
                  >
                    {ollamaLoading && <Loader2 className="animate-spin" />}
                    Refresh status
                  </Button>
                  <Button
                    type="button"
                    onClick={() => void onTestOllama()}
                    disabled={ollamaTesting || ollamaLoading}
                  >
                    {ollamaTesting && <Loader2 className="animate-spin" />}
                    Test Ollama Connection
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => void onSelectModel()}
                    disabled={!selectedModel || ollamaLoading}
                  >
                    Use selected model
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {activeTab === "password" && (
            <Card>
              <CardHeader>
                <CardTitle>Password</CardTitle>
                <CardDescription>Change your account password</CardDescription>
              </CardHeader>
              <CardContent>
                <form
                  onSubmit={passwordForm.handleSubmit(onPasswordSubmit)}
                  className="max-w-md space-y-4"
                >
                  <div className="space-y-2">
                    <Label htmlFor="current_password">Current password</Label>
                    <Input
                      id="current_password"
                      type="password"
                      {...passwordForm.register("current_password")}
                    />
                    {passwordForm.formState.errors.current_password && (
                      <p className="text-sm text-destructive">
                        {passwordForm.formState.errors.current_password.message}
                      </p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="new_password">New password</Label>
                    <Input
                      id="new_password"
                      type="password"
                      {...passwordForm.register("new_password")}
                    />
                    {passwordForm.formState.errors.new_password && (
                      <p className="text-sm text-destructive">
                        {passwordForm.formState.errors.new_password.message}
                      </p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="confirm_password">Confirm new password</Label>
                    <Input
                      id="confirm_password"
                      type="password"
                      {...passwordForm.register("confirm_password")}
                    />
                    {passwordForm.formState.errors.confirm_password && (
                      <p className="text-sm text-destructive">
                        {passwordForm.formState.errors.confirm_password.message}
                      </p>
                    )}
                  </div>
                  <Button type="submit" disabled={passwordSaving}>
                    {passwordSaving && <Loader2 className="animate-spin" />}
                    Update password
                  </Button>
                </form>
              </CardContent>
            </Card>
          )}

          {activeTab === "notifications" && (
            <Card>
              <CardHeader>
                <CardTitle>Notifications</CardTitle>
                <CardDescription>Configure email and in-app alerts</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {[
                  { id: "doc", label: "Document processing complete" },
                  { id: "chat", label: "New chat mentions" },
                  { id: "security", label: "Security alerts" },
                  { id: "weekly", label: "Weekly usage summary" },
                ].map((item) => (
                  <label
                    key={item.id}
                    className="flex items-center justify-between rounded-lg border border-border px-4 py-3"
                  >
                    <span className="text-sm">{item.label}</span>
                    <input
                      type="checkbox"
                      defaultChecked
                      className="h-4 w-4 accent-primary"
                    />
                  </label>
                ))}
              </CardContent>
            </Card>
          )}

          {activeTab === "theme" && (
            <Card>
              <CardHeader>
                <CardTitle>Theme</CardTitle>
                <CardDescription>
                  Current: {resolved} mode
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid max-w-md gap-3 sm:grid-cols-3">
                  {(
                    [
                      { mode: "light" as ThemeMode, icon: Sun, label: "Light" },
                      { mode: "dark" as ThemeMode, icon: Moon, label: "Dark" },
                      { mode: "system" as ThemeMode, icon: Palette, label: "System" },
                    ] as const
                  ).map(({ mode, icon: Icon, label }) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setTheme(mode)}
                      className={cn(
                        "flex flex-col items-center gap-2 rounded-xl border p-4 transition-colors",
                        theme === mode
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-border hover:border-primary/40"
                      )}
                    >
                      <Icon className="h-6 w-6" />
                      <span className="text-sm font-medium">{label}</span>
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {activeTab === "language" && (
            <Card>
              <CardHeader>
                <CardTitle>Language</CardTitle>
                <CardDescription>Select your preferred language</CardDescription>
              </CardHeader>
              <CardContent className="max-w-md">
                <select
                  className="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                  defaultValue="en"
                >
                  <option value="en">English</option>
                  <option value="es">Español</option>
                  <option value="fr">Français</option>
                  <option value="de">Deutsch</option>
                </select>
              </CardContent>
            </Card>
          )}

          {activeTab === "danger" && (
            <Card className="border-destructive/30">
              <CardHeader>
                <CardTitle className="text-destructive">Danger Zone</CardTitle>
                <CardDescription>
                  Irreversible actions for your account
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-col gap-4 rounded-lg border border-destructive/30 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="font-medium">Export all data</p>
                    <p className="text-sm text-muted-foreground">
                      Download a copy of your documents and chat history
                    </p>
                  </div>
                  <Button variant="outline">Export</Button>
                </div>
                <div className="flex flex-col gap-4 rounded-lg border border-destructive/30 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="font-medium text-destructive">Delete account</p>
                    <p className="text-sm text-muted-foreground">
                      Permanently remove your account and all associated data
                    </p>
                  </div>
                  <Button variant="destructive">Delete account</Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
