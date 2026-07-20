import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  Building2,
  HardDrive,
  KeyRound,
  ScrollText,
  Shield,
  Users,
  UsersRound,
  CreditCard,
} from "lucide-react";
import {
  adminApi,
  type AdminOrganization,
  type AdminTeam,
  type AdminUser,
  type ApiKeyItem,
  type AuditLogItem,
  type StorageDashboard,
} from "@/services/api/admin";
import { getErrorMessage } from "@/services/api/client";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Input } from "@/components/common/Input";
import { Loader } from "@/components/common/Loader";
import { Modal } from "@/components/common/Modal";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/common/Card";
import { cn, formatBytes, initials } from "@/lib/utils";
import { toast } from "sonner";

type TabId =
  | "organizations"
  | "teams"
  | "users"
  | "permissions"
  | "storage"
  | "audit"
  | "api-keys"
  | "subscription";

const tabs: { id: TabId; label: string; icon: typeof Building2 }[] = [
  { id: "organizations", label: "Organizations", icon: Building2 },
  { id: "teams", label: "Teams", icon: UsersRound },
  { id: "users", label: "Users", icon: Users },
  { id: "permissions", label: "Permissions", icon: Shield },
  { id: "storage", label: "Storage", icon: HardDrive },
  { id: "audit", label: "Audit Logs", icon: ScrollText },
  { id: "api-keys", label: "API Keys", icon: KeyRound },
  { id: "subscription", label: "Subscription", icon: CreditCard },
];

const permissionMatrix = [
  { role: "admin", permissions: ["admin:all", "users:*", "documents:*", "analytics:*"] },
  { role: "manager", permissions: ["users:read", "documents:*", "chat:*", "agents:*"] },
  { role: "employee", permissions: ["documents:read/write", "chat:*", "ocr:*", "meetings:*"] },
];

const PATH_TAB: Record<string, TabId> = {
  "/admin/organizations": "organizations",
  "/admin/teams": "teams",
  "/admin/users": "users",
  "/admin/storage": "storage",
  "/admin/audit": "audit",
  "/admin/api-keys": "api-keys",
  "/admin/subscription": "subscription",
};

export function AdminPage() {
  const location = useLocation();
  const initialTab = PATH_TAB[location.pathname] ?? "organizations";
  const [tab, setTab] = useState<TabId>(initialTab);

  useEffect(() => {
    setTab(PATH_TAB[location.pathname] ?? tab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);
  const [loading, setLoading] = useState(true);
  const [orgs, setOrgs] = useState<AdminOrganization[]>([]);
  const [selectedOrgId, setSelectedOrgId] = useState<string>("");
  const [teams, setTeams] = useState<AdminTeam[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState<string>("");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [audit, setAudit] = useState<AuditLogItem[]>([]);
  const [apiKeys, setApiKeys] = useState<ApiKeyItem[]>([]);
  const [storage, setStorage] = useState<StorageDashboard | null>(null);
  const [subscription, setSubscription] = useState<Record<string, unknown> | null>(
    null,
  );
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("employee");
  const [newOrgName, setNewOrgName] = useState("");
  const [newTeamName, setNewTeamName] = useState("");
  const [newKeyName, setNewKeyName] = useState("");
  const [revealedKey, setRevealedKey] = useState<string | null>(null);

  const selectedOrg = useMemo(
    () => orgs.find((o) => o.id === selectedOrgId) || orgs[0],
    [orgs, selectedOrgId],
  );

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [orgRes, userRes, auditRes, keyRes, storageRes, subRes] =
        await Promise.all([
          adminApi.organizations.list(),
          adminApi.users.list({ limit: 100 }),
          adminApi.audit({ limit: 50 }),
          adminApi.apiKeys.list(),
          adminApi.storage(),
          adminApi.subscription(),
        ]);
      const orgList = orgRes.data.data || [];
      setOrgs(orgList);
      if (!selectedOrgId && orgList[0]) setSelectedOrgId(orgList[0].id);
      setUsers(userRes.data.data?.items || []);
      setAudit(auditRes.data.data?.items || []);
      setApiKeys(keyRes.data.data || []);
      setStorage(storageRes.data.data || null);
      setSubscription(subRes.data.data || null);

      const orgId = selectedOrgId || orgList[0]?.id;
      if (orgId) {
        const teamRes = await adminApi.teams.list(orgId);
        const teamList = teamRes.data.data || [];
        setTeams(teamList);
        if (!selectedTeamId && teamList[0]) setSelectedTeamId(teamList[0].id);
      }
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [selectedOrgId, selectedTeamId]);

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedOrgId) return;
    (async () => {
      try {
        const teamRes = await adminApi.teams.list(selectedOrgId);
        setTeams(teamRes.data.data || []);
      } catch (error) {
        toast.error(getErrorMessage(error));
      }
    })();
  }, [selectedOrgId]);

  async function createOrg() {
    if (!newOrgName.trim()) return;
    try {
      await adminApi.organizations.create({ name: newOrgName.trim() });
      setNewOrgName("");
      toast.success("Organization created");
      await refresh();
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  async function createTeam() {
    if (!newTeamName.trim() || !selectedOrg) return;
    try {
      await adminApi.teams.create({
        name: newTeamName.trim(),
        organization_id: selectedOrg.id,
      });
      setNewTeamName("");
      toast.success("Team created");
      await refresh();
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  async function inviteUser() {
    if (!inviteEmail.trim()) return;
    try {
      await adminApi.users.invite({
        email: inviteEmail.trim(),
        role: inviteRole,
        organization_id: selectedOrg?.id,
        team_id: selectedTeamId || undefined,
      });
      setInviteOpen(false);
      setInviteEmail("");
      toast.success("Invitation sent");
      await refresh();
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  async function setUserStatus(user: AdminUser, status: string) {
    try {
      await adminApi.users.update(user.id, { status });
      toast.success(`User ${status}`);
      await refresh();
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  async function createApiKey() {
    if (!newKeyName.trim()) return;
    try {
      const { data } = await adminApi.apiKeys.create({
        name: newKeyName.trim(),
        scopes: ["read", "write"],
      });
      setNewKeyName("");
      setRevealedKey(data.data?.api_key || null);
      toast.success("API key created — copy it now");
      await refresh();
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  if (loading && !orgs.length) {
    return <Loader label="Loading admin console..." />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold tracking-tight">
            Admin Console
          </h1>
          <p className="mt-1 text-muted-foreground">
            Multi-tenant SaaS administration — organizations, teams, users, and
            security
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-sm text-muted-foreground">Organization</label>
          <select
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={selectedOrg?.id || ""}
            onChange={(e) => setSelectedOrgId(e.target.value)}
          >
            {orgs.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
          <label className="text-sm text-muted-foreground">Team</label>
          <select
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={selectedTeamId}
            onChange={(e) => setSelectedTeamId(e.target.value)}
          >
            <option value="">All teams</option>
            {teams.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          <Button onClick={() => setInviteOpen(true)}>Invite user</Button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Users", value: users.length, icon: Users },
          { label: "Organizations", value: orgs.length, icon: Building2 },
          {
            label: "Storage",
            value: formatBytes(storage?.used_bytes || 0),
            icon: HardDrive,
          },
          {
            label: "Plan",
            value: String(storage?.subscription?.plan || "—"),
            icon: CreditCard,
          },
        ].map((stat) => {
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
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="flex flex-wrap gap-2 border-b border-border pb-2">
        {tabs.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={cn(
                "inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm transition",
                tab === t.id
                  ? "bg-primary/15 text-primary"
                  : "text-muted-foreground hover:bg-muted/40",
              )}
            >
              <Icon className="h-4 w-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      {tab === "organizations" && (
        <Card>
          <CardHeader>
            <CardTitle>Organizations</CardTitle>
            <CardDescription>
              Branding, domain, timezone, and AI/storage settings
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                placeholder="New organization name"
                value={newOrgName}
                onChange={(e) => setNewOrgName(e.target.value)}
              />
              <Button onClick={() => void createOrg()}>Create</Button>
            </div>
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/30">
                    <th className="px-4 py-3 text-left">Name</th>
                    <th className="px-4 py-3 text-left">Domain</th>
                    <th className="px-4 py-3 text-left">Region</th>
                    <th className="px-4 py-3 text-left">Timezone</th>
                    <th className="px-4 py-3 text-left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {orgs.map((o) => (
                    <tr key={o.id} className="border-b border-border/60">
                      <td className="px-4 py-3 font-medium">{o.name}</td>
                      <td className="px-4 py-3">{o.domain || "—"}</td>
                      <td className="px-4 py-3">{o.region}</td>
                      <td className="px-4 py-3">{o.timezone}</td>
                      <td className="px-4 py-3">
                        <Badge>{o.status}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "teams" && (
        <Card>
          <CardHeader>
            <CardTitle>Teams</CardTitle>
            <CardDescription>
              Teams under {selectedOrg?.name || "organization"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                placeholder="New team name"
                value={newTeamName}
                onChange={(e) => setNewTeamName(e.target.value)}
              />
              <Button onClick={() => void createTeam()}>Create</Button>
            </div>
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/30">
                    <th className="px-4 py-3 text-left">Name</th>
                    <th className="px-4 py-3 text-left">Description</th>
                    <th className="px-4 py-3 text-left">Manager</th>
                  </tr>
                </thead>
                <tbody>
                  {teams.map((t) => (
                    <tr key={t.id} className="border-b border-border/60">
                      <td className="px-4 py-3 font-medium">{t.name}</td>
                      <td className="px-4 py-3">{t.description || "—"}</td>
                      <td className="px-4 py-3">{t.manager_id || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "users" && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Users</CardTitle>
              <CardDescription>Tenant-scoped directory</CardDescription>
            </div>
            <Button onClick={() => setInviteOpen(true)}>Invite</Button>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/30">
                    <th className="px-4 py-3 text-left">User</th>
                    <th className="px-4 py-3 text-left">Roles</th>
                    <th className="px-4 py-3 text-left">Status</th>
                    <th className="px-4 py-3 text-left">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="border-b border-border/60">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/15 text-xs font-medium text-primary">
                            {initials(u.full_name)}
                          </div>
                          <div>
                            <div className="font-medium">{u.full_name}</div>
                            <div className="text-muted-foreground">{u.email}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          {u.roles.map((r) => (
                            <Badge key={r}>{r}</Badge>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge>{u.status}</Badge>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => void setUserStatus(u, "suspended")}
                          >
                            Suspend
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => void setUserStatus(u, "active")}
                          >
                            Activate
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => void setUserStatus(u, "disabled")}
                          >
                            Disable
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "permissions" && (
        <Card>
          <CardHeader>
            <CardTitle>Permission Matrix</CardTitle>
            <CardDescription>Role → permission mapping (RBAC)</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/30">
                    <th className="px-4 py-3 text-left">Role</th>
                    <th className="px-4 py-3 text-left">Permissions</th>
                  </tr>
                </thead>
                <tbody>
                  {permissionMatrix.map((row) => (
                    <tr key={row.role} className="border-b border-border/60">
                      <td className="px-4 py-3 font-medium">{row.role}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          {row.permissions.map((p) => (
                            <Badge key={p}>{p}</Badge>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "storage" && storage && (
        <Card>
          <CardHeader>
            <CardTitle>Storage Dashboard</CardTitle>
            <CardDescription>
              Quota {formatBytes(storage.quota_bytes)} · Used{" "}
              {formatBytes(storage.used_bytes)}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(storage.breakdown || {}).map(([k, v]) => (
              <div key={k} className="rounded-lg border border-border p-4">
                <div className="text-sm text-muted-foreground capitalize">{k}</div>
                <div className="mt-1 text-xl font-semibold">{formatBytes(v)}</div>
              </div>
            ))}
            {Object.entries(storage.usage_limits || {})
              .filter(([k]) => k.startsWith("max_"))
              .map(([k, v]) => (
                <div key={k} className="rounded-lg border border-border p-4">
                  <div className="text-sm text-muted-foreground">{k}</div>
                  <div className="mt-1 text-xl font-semibold">{v}</div>
                </div>
              ))}
          </CardContent>
        </Card>
      )}

      {tab === "audit" && (
        <Card>
          <CardHeader>
            <CardTitle>Audit Viewer</CardTitle>
            <CardDescription>Admin and security events for this tenant</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/30">
                    <th className="px-4 py-3 text-left">Time</th>
                    <th className="px-4 py-3 text-left">Action</th>
                    <th className="px-4 py-3 text-left">Resource</th>
                    <th className="px-4 py-3 text-left">Result</th>
                  </tr>
                </thead>
                <tbody>
                  {audit.map((a) => (
                    <tr key={a.id} className="border-b border-border/60">
                      <td className="px-4 py-3 whitespace-nowrap">
                        {a.created_at
                          ? new Date(a.created_at).toLocaleString()
                          : "—"}
                      </td>
                      <td className="px-4 py-3">{a.action}</td>
                      <td className="px-4 py-3">
                        {a.resource_type || "—"}{" "}
                        {a.resource_id ? `(${a.resource_id.slice(0, 8)})` : ""}
                      </td>
                      <td className="px-4 py-3">
                        <Badge>{a.success ? "ok" : "fail"}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "api-keys" && (
        <Card>
          <CardHeader>
            <CardTitle>API Key Manager</CardTitle>
            <CardDescription>
              Generate, rotate, and revoke tenant API keys
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                placeholder="Key name"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
              />
              <Button onClick={() => void createApiKey()}>Generate</Button>
            </div>
            {revealedKey && (
              <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
                Copy this key now — it will not be shown again:
                <code className="mt-2 block break-all font-mono">{revealedKey}</code>
              </div>
            )}
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/30">
                    <th className="px-4 py-3 text-left">Name</th>
                    <th className="px-4 py-3 text-left">Prefix</th>
                    <th className="px-4 py-3 text-left">Scopes</th>
                    <th className="px-4 py-3 text-left">Usage</th>
                    <th className="px-4 py-3 text-left">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {apiKeys.map((k) => (
                    <tr key={k.id} className="border-b border-border/60">
                      <td className="px-4 py-3">{k.name}</td>
                      <td className="px-4 py-3 font-mono">{k.key_prefix}…</td>
                      <td className="px-4 py-3">{(k.scopes || []).join(", ")}</td>
                      <td className="px-4 py-3">{k.usage_count}</td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={async () => {
                              try {
                                const { data } = await adminApi.apiKeys.rotate(k.id);
                                setRevealedKey(data.data?.api_key || null);
                                toast.success("Key rotated");
                                await refresh();
                              } catch (error) {
                                toast.error(getErrorMessage(error));
                              }
                            }}
                          >
                            Rotate
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={async () => {
                              try {
                                await adminApi.apiKeys.remove(k.id);
                                toast.success("Key deleted");
                                await refresh();
                              } catch (error) {
                                toast.error(getErrorMessage(error));
                              }
                            }}
                          >
                            Disable
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "subscription" && (
        <Card>
          <CardHeader>
            <CardTitle>Subscription & Usage</CardTitle>
            <CardDescription>
              Architecture placeholder — no payment gateway (Module 12)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3">
              {["free", "starter", "professional", "enterprise"].map((plan) => (
                <div
                  key={plan}
                  className={cn(
                    "rounded-lg border p-4",
                    storage?.subscription?.plan === plan
                      ? "border-primary bg-primary/5"
                      : "border-border",
                  )}
                >
                  <div className="font-semibold capitalize">{plan}</div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    {storage?.subscription?.plan === plan
                      ? "Current plan"
                      : "Available"}
                  </div>
                </div>
              ))}
            </div>
            <pre className="overflow-auto rounded-lg border border-border bg-muted/20 p-4 text-xs">
              {JSON.stringify(subscription, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}

      <Modal
        open={inviteOpen}
        onOpenChange={setInviteOpen}
        title="Invite user"
      >
        <div className="space-y-3">
          <Input
            placeholder="Email"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
          />
          <select
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={inviteRole}
            onChange={(e) => setInviteRole(e.target.value)}
          >
            <option value="employee">employee</option>
            <option value="manager">manager</option>
            <option value="admin">admin</option>
          </select>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setInviteOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => void inviteUser()}>Send invite</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
