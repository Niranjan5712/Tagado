import { FormEvent, useEffect, useMemo, useState } from "react";
import { Navigate, useParams } from "react-router-dom";

import {
  type RoleInfo,
  type User,
  type WorkspaceSettings,
  type WorkspaceUser,
  createUser,
  fetchMe,
  fetchSettings,
  fetchUsers,
  regenerateClaudeLink,
  removeUser,
  resetSampleData,
  saveSettings,
  updateUserRole,
} from "@/api/client";

const SECTIONS = [
  "branding",
  "payments",
  "reminders",
  "claude",
  "users",
  "data",
] as const;

type Section = (typeof SECTIONS)[number];

const SECTION_META: Record<Section, { title: string; description: string }> = {
  branding: {
    title: "Branding & identity",
    description: "Business identity, how you appear to clients, and the look of this workspace.",
  },
  payments: {
    title: "Payment details",
    description: "Bank and UPI information shown when clients are asked to pay.",
  },
  reminders: {
    title: "Reminders",
    description: "When approved follow-ups are sent during the day (India time).",
  },
  claude: {
    title: "Connect Claude",
    description: "Let Claude draft invoice follow-ups into Tagado. Nothing sends until you approve.",
  },
  users: {
    title: "Users & roles",
    description: "Invite people to this workspace and decide what they can do.",
  },
  data: {
    title: "Data governance",
    description: "Retention, access, and how invoice data is handled in this workspace.",
  },
};

const ACCENT_PRESETS = ["#0f6e56", "#0b4f8a", "#7a3e12", "#5b2c6f", "#1f2937"] as const;

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Could not read that file"));
    reader.readAsDataURL(file);
  });
}

export function Settings() {
  const { section } = useParams<{ section?: string }>();
  const active = (section || "branding") as Section;
  const [settings, setSettings] = useState<WorkspaceSettings | null>(null);
  const [me, setMe] = useState<User | null>(null);
  const [users, setUsers] = useState<WorkspaceUser[]>([]);
  const [roles, setRoles] = useState<RoleInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [newUser, setNewUser] = useState({
    name: "",
    email: "",
    password: "",
    role: "operator",
  });

  useEffect(() => {
    fetchSettings()
      .then(setSettings)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load settings"));
    fetchMe()
      .then(setMe)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (active !== "users") return;
    fetchUsers()
      .then((data) => {
        setUsers(data.users);
        setRoles(data.roles);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load users"));
  }, [active]);

  useEffect(() => {
    if (!settings) return;
    document.documentElement.style.setProperty("--accent", settings.accent_color || "#0f6e56");
    const existing = document.querySelector<HTMLLinkElement>("link[data-tagado-favicon]");
    if (settings.favicon_data_url) {
      const link = existing ?? document.createElement("link");
      link.rel = "icon";
      link.href = settings.favicon_data_url;
      link.dataset.tagadoFavicon = "true";
      if (!existing) document.head.appendChild(link);
    } else if (existing) {
      existing.remove();
    }
  }, [settings]);

  const meta = useMemo(() => SECTION_META[active], [active]);

  if (section && !SECTIONS.includes(section as Section)) {
    return <Navigate to="/settings/branding" replace />;
  }

  async function handleSave(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!settings) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const saved = await saveSettings({
        business_name: settings.business_name,
        sender_name: settings.sender_name,
        reply_to_email: settings.reply_to_email,
        bank_account_name: settings.bank_account_name,
        bank_account_number: settings.bank_account_number,
        ifsc: settings.ifsc,
        upi_id: settings.upi_id,
        udyam_number: settings.udyam_number,
        send_hour_ist: settings.send_hour_ist,
        send_minute_ist: settings.send_minute_ist,
        logo_data_url: settings.logo_data_url,
        favicon_data_url: settings.favicon_data_url,
        accent_color: settings.accent_color,
        retention_days_paid: settings.retention_days_paid,
        retention_keep_audit: settings.retention_keep_audit,
      });
      setSettings(saved);
      setMessage("Settings saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save settings");
    } finally {
      setBusy(false);
    }
  }

  async function copyLink(): Promise<void> {
    if (!settings) return;
    await navigator.clipboard.writeText(settings.claude_connection_url);
    setMessage("Claude connection link copied.");
  }

  async function handleRegenerate(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const saved = await regenerateClaudeLink();
      setSettings(saved);
      setMessage("New Claude connection link created. Update it in Claude.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create a new link");
    } finally {
      setBusy(false);
    }
  }

  async function handleReset(): Promise<void> {
    if (!window.confirm("Restore the sample invoices and client history for this review workspace?")) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await resetSampleData();
      setSettings(await fetchSettings());
      setMessage(result.summary);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reset sample data");
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateUser(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await createUser(newUser);
      const data = await fetchUsers();
      setUsers(data.users);
      setNewUser({ name: "", email: "", password: "", role: "operator" });
      setMessage("User added to this workspace.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add user");
    } finally {
      setBusy(false);
    }
  }

  if (!settings && !error) {
    return <p className="text-sm text-slate-500">Loading settings…</p>;
  }

  if (!settings) {
    return <p className="text-sm text-rose-700">{error}</p>;
  }

  const isOwner = (me?.role || "owner") === "owner";

  return (
    <div className="space-y-6">
      <section>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--accent)]">Settings</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">{meta.title}</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-600">{meta.description}</p>
      </section>

      {error ? <p className="text-sm text-rose-700">{error}</p> : null}
      {message ? <p className="text-sm text-emerald-700">{message}</p> : null}

      {active === "branding" ? (
        <form onSubmit={handleSave} className="space-y-4 rounded-2xl border border-[var(--line)] bg-[var(--card)] p-5 shadow-sm">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Business name"
              hint="Shown on client payment pages and reminder footers."
              value={settings.business_name}
              onChange={(value) => setSettings({ ...settings, business_name: value })}
            />
            <Field
              label="Sender name"
              hint='From-name on reminders, e.g. “Priya at Pixelcraft Studio”.'
              value={settings.sender_name}
              onChange={(value) => setSettings({ ...settings, sender_name: value })}
            />
            <Field
              label="Reply-to email"
              hint="Where client replies and payment questions should land."
              value={settings.reply_to_email ?? ""}
              onChange={(value) => setSettings({ ...settings, reply_to_email: value })}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm font-medium">
              Logo
              <span className="mt-1 block text-xs font-normal text-slate-500">
                Used in the workspace sidebar and client payment pages.
              </span>
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp,image/svg+xml"
                className="mt-2 block w-full text-sm"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (!file) return;
                  void readFileAsDataUrl(file).then((url) =>
                    setSettings({ ...settings, logo_data_url: url }),
                  );
                }}
              />
              {settings.logo_data_url ? (
                <div className="mt-3 flex items-center gap-3">
                  <img src={settings.logo_data_url} alt="Logo preview" className="h-12 w-12 rounded-lg object-contain" />
                  <button
                    type="button"
                    className="text-xs font-medium text-slate-600"
                    onClick={() => setSettings({ ...settings, logo_data_url: null })}
                  >
                    Remove logo
                  </button>
                </div>
              ) : null}
            </label>

            <label className="block text-sm font-medium">
              Favicon
              <span className="mt-1 block text-xs font-normal text-slate-500">
                Browser tab icon for Tagado in this workspace.
              </span>
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp,image/x-icon,image/svg+xml"
                className="mt-2 block w-full text-sm"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (!file) return;
                  void readFileAsDataUrl(file).then((url) =>
                    setSettings({ ...settings, favicon_data_url: url }),
                  );
                }}
              />
              {settings.favicon_data_url ? (
                <div className="mt-3 flex items-center gap-3">
                  <img
                    src={settings.favicon_data_url}
                    alt="Favicon preview"
                    className="h-8 w-8 rounded object-contain"
                  />
                  <button
                    type="button"
                    className="text-xs font-medium text-slate-600"
                    onClick={() => setSettings({ ...settings, favicon_data_url: null })}
                  >
                    Remove favicon
                  </button>
                </div>
              ) : null}
            </label>
          </div>

          <div>
            <p className="text-sm font-medium">App accent color</p>
            <p className="mt-1 text-xs text-slate-500">Used for navigation highlights and primary actions.</p>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              {ACCENT_PRESETS.map((color) => (
                <button
                  key={color}
                  type="button"
                  aria-label={`Use accent ${color}`}
                  className={`h-8 w-8 rounded-full border-2 ${
                    settings.accent_color === color ? "border-[var(--ink)]" : "border-transparent"
                  }`}
                  style={{ backgroundColor: color }}
                  onClick={() => setSettings({ ...settings, accent_color: color })}
                />
              ))}
              <input
                type="color"
                value={settings.accent_color || "#0f6e56"}
                onChange={(event) => setSettings({ ...settings, accent_color: event.target.value })}
                className="h-8 w-12 cursor-pointer rounded border border-[var(--line)] bg-white"
              />
              <span className="text-xs text-slate-500">{settings.accent_color}</span>
            </div>
          </div>

          <div className="rounded-xl border border-[var(--line)] bg-[var(--accent-soft)]/50 p-4">
            <p className="text-sm font-semibold">Client-facing preview</p>
            <p className="mt-1 text-xs text-slate-600">
              This is how your brand shows up when a client opens a payment request.
            </p>
            <div className="mt-4 rounded-xl bg-white p-4 shadow-sm">
              <div className="flex items-center gap-3">
                {settings.logo_data_url ? (
                  <img src={settings.logo_data_url} alt="" className="h-10 w-10 rounded-lg object-contain" />
                ) : (
                  <span
                    className="flex h-10 w-10 items-center justify-center rounded-lg text-sm font-bold text-white"
                    style={{ backgroundColor: settings.accent_color }}
                  >
                    Tg
                  </span>
                )}
                <div>
                  <p className="text-xs uppercase tracking-[0.14em]" style={{ color: settings.accent_color }}>
                    Payment request
                  </p>
                  <p className="mt-1 text-lg font-semibold">from {settings.business_name || "Your business"}</p>
                </div>
              </div>
              <p className="mt-3 text-sm text-slate-600">
                Sent by {settings.sender_name || "Your sender name"} · reply to{" "}
                {settings.reply_to_email || "your reply-to email"}
              </p>
            </div>
          </div>
          <SaveButton busy={busy} />
        </form>
      ) : null}

      {active === "payments" ? (
        <form onSubmit={handleSave} className="space-y-4 rounded-2xl border border-[var(--line)] bg-[var(--card)] p-5 shadow-sm">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Account name"
              value={settings.bank_account_name ?? ""}
              onChange={(value) => setSettings({ ...settings, bank_account_name: value })}
            />
            <Field
              label="Account number"
              value={settings.bank_account_number ?? ""}
              onChange={(value) => setSettings({ ...settings, bank_account_number: value })}
            />
            <Field
              label="IFSC"
              value={settings.ifsc ?? ""}
              onChange={(value) => setSettings({ ...settings, ifsc: value })}
            />
            <Field
              label="UPI ID (optional)"
              hint="Shown as a QR only when the outstanding amount is ₹1,00,000 or less."
              value={settings.upi_id ?? ""}
              onChange={(value) => setSettings({ ...settings, upi_id: value })}
            />
            <Field
              label="Udyam number (optional)"
              hint="Enables the MSME note on final reminders after you turn it on per invoice."
              value={settings.udyam_number ?? ""}
              onChange={(value) => setSettings({ ...settings, udyam_number: value })}
            />
          </div>
          {settings.msme_note_preview ? (
            <div className="rounded-xl bg-emerald-50 p-4 text-sm text-emerald-950">
              <p className="font-medium">MSME note preview</p>
              <p className="mt-1 text-xs text-emerald-800">Template wording — pending CA review.</p>
              <p className="mt-2 leading-relaxed">{settings.msme_note_preview}</p>
            </div>
          ) : (
            <p className="text-sm text-slate-600">
              Add a Udyam number to unlock the MSME note option on final reminders.
            </p>
          )}
          <SaveButton busy={busy} />
        </form>
      ) : null}

      {active === "reminders" ? (
        <form onSubmit={handleSave} className="space-y-4 rounded-2xl border border-[var(--line)] bg-[var(--card)] p-5 shadow-sm">
          <p className="text-sm text-slate-600">
            Approved reminders are sent Monday–Saturday in this window. Sundays move to Monday.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm font-medium">
              Send hour (IST)
              <select
                className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2"
                value={settings.send_hour_ist}
                onChange={(event) =>
                  setSettings({ ...settings, send_hour_ist: Number(event.target.value) })
                }
              >
                {Array.from({ length: 11 }, (_, index) => index + 9).map((hour) => (
                  <option key={hour} value={hour}>
                    {hour}:00
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-medium">
              Send minute
              <select
                className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2"
                value={settings.send_minute_ist}
                onChange={(event) =>
                  setSettings({ ...settings, send_minute_ist: Number(event.target.value) })
                }
              >
                {[0, 15, 30, 45].map((minute) => (
                  <option key={minute} value={minute}>
                    {String(minute).padStart(2, "0")}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className="text-sm text-slate-600">
            Current schedule: {settings.send_hour_ist}:
            {String(settings.send_minute_ist).padStart(2, "0")} IST
          </p>
          <SaveButton busy={busy} />
        </form>
      ) : null}

      {active === "claude" ? (
        <section className="space-y-4 rounded-2xl border border-[var(--line)] bg-[var(--card)] p-5 shadow-sm">
          <p className="text-sm text-slate-600">
            Claude drafts follow-ups into your Tagado workspace. You stay in control of approval and
            sending. This private link is the only way Claude can reach this workspace.
          </p>
          <div className="rounded-xl border border-[var(--line)] bg-[var(--paper)] p-3">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Private Claude connection link
            </p>
            <p className="mt-2 break-all text-sm text-slate-800">{settings.claude_connection_url}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void copyLink()}
              className="rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white"
            >
              Copy link
            </button>
            <button
              type="button"
              onClick={() => void handleRegenerate()}
              disabled={busy}
              className="rounded-lg border border-[var(--line)] px-3 py-2 text-sm font-medium"
            >
              Create new link
            </button>
          </div>
          <ol className="list-decimal space-y-2 pl-5 text-sm text-slate-700">
            <li>In Claude, open Settings → Connectors.</li>
            <li>Add a custom connector named Tagado and paste the link above.</li>
            <li>Connect, then ask Claude: “What can Tagado do?”</li>
          </ol>
        </section>
      ) : null}

      {active === "users" ? (
        <section className="space-y-4">
          <article className="rounded-2xl border border-[var(--line)] bg-[var(--card)] p-5 shadow-sm">
            <h2 className="text-lg font-semibold">People in this workspace</h2>
            <ul className="mt-4 divide-y divide-[var(--line)]">
              {users.map((user) => (
                <li key={user.id} className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm font-medium">
                      {user.name}
                      {me?.id === user.id ? " (you)" : ""}
                    </p>
                    <p className="text-xs text-slate-500">{user.email}</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <select
                      className="rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm"
                      value={user.role}
                      disabled={!isOwner || me?.id === user.id}
                      onChange={(event) => {
                        void updateUserRole(user.id, event.target.value)
                          .then(async () => {
                            const data = await fetchUsers();
                            setUsers(data.users);
                            setMessage("Role updated.");
                          })
                          .catch((err: unknown) =>
                            setError(err instanceof Error ? err.message : "Could not update role"),
                          );
                      }}
                    >
                      {(roles.length ? roles : [
                        { id: "owner", label: "Owner" },
                        { id: "operator", label: "Operator" },
                        { id: "viewer", label: "Viewer" },
                      ]).map((role) => (
                        <option key={role.id} value={role.id}>
                          {role.label}
                        </option>
                      ))}
                    </select>
                    {isOwner && me?.id !== user.id ? (
                      <button
                        type="button"
                        className="rounded-lg border border-[var(--line)] px-3 py-2 text-sm"
                        onClick={() => {
                          if (!window.confirm(`Remove ${user.name} from this workspace?`)) return;
                          void removeUser(user.id)
                            .then(async () => {
                              const data = await fetchUsers();
                              setUsers(data.users);
                              setMessage("User removed.");
                            })
                            .catch((err: unknown) =>
                              setError(err instanceof Error ? err.message : "Could not remove user"),
                            );
                        }}
                      >
                        Remove
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
            {roles.length > 0 ? (
              <ul className="mt-4 space-y-2 text-xs text-slate-600">
                {roles.map((role) => (
                  <li key={role.id}>
                    <strong>{role.label}:</strong> {role.description}
                  </li>
                ))}
              </ul>
            ) : null}
          </article>

          {isOwner ? (
            <form
              onSubmit={handleCreateUser}
              className="space-y-4 rounded-2xl border border-[var(--line)] bg-[var(--card)] p-5 shadow-sm"
            >
              <h2 className="text-lg font-semibold">Add user</h2>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field
                  label="Name"
                  value={newUser.name}
                  onChange={(value) => setNewUser({ ...newUser, name: value })}
                />
                <Field
                  label="Email"
                  value={newUser.email}
                  onChange={(value) => setNewUser({ ...newUser, email: value })}
                />
                <Field
                  label="Temporary password"
                  value={newUser.password}
                  onChange={(value) => setNewUser({ ...newUser, password: value })}
                  hint="At least 8 characters. Share it securely."
                />
                <label className="block text-sm font-medium">
                  Role
                  <select
                    className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2"
                    value={newUser.role}
                    onChange={(event) => setNewUser({ ...newUser, role: event.target.value })}
                  >
                    <option value="operator">Operator</option>
                    <option value="viewer">Viewer</option>
                  </select>
                </label>
              </div>
              <SaveButton busy={busy} label="Add user" />
            </form>
          ) : (
            <p className="text-sm text-slate-600">Only owners can add or remove people.</p>
          )}
        </section>
      ) : null}

      {active === "data" ? (
        <section className="space-y-4">
          <form onSubmit={handleSave} className="space-y-4 rounded-2xl border border-[var(--line)] bg-[var(--card)] p-5 shadow-sm">
            <h2 className="text-lg font-semibold">Retention</h2>
            <p className="text-sm text-slate-600">
              Control how long settled invoice records stay available for history and Claude context.
            </p>
            <label className="block text-sm font-medium">
              Keep paid / cancelled invoices for
              <select
                className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 sm:max-w-xs"
                value={settings.retention_days_paid}
                onChange={(event) =>
                  setSettings({ ...settings, retention_days_paid: Number(event.target.value) })
                }
              >
                <option value={90}>90 days</option>
                <option value={180}>180 days</option>
                <option value={365}>1 year</option>
                <option value={730}>2 years</option>
                <option value={1825}>5 years</option>
              </select>
            </label>
            <label className="flex items-start gap-3 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={settings.retention_keep_audit}
                onChange={(event) =>
                  setSettings({ ...settings, retention_keep_audit: event.target.checked })
                }
              />
              <span>
                <span className="font-medium">Keep audit history with retained invoices</span>
                <span className="mt-1 block text-xs text-slate-500">
                  Timeline events stay attached while the invoice is retained.
                </span>
              </span>
            </label>
            <SaveButton busy={busy} />
          </form>

          <article className="rounded-2xl border border-[var(--line)] bg-[var(--card)] p-5 shadow-sm">
            <h2 className="text-lg font-semibold">Governance rules</h2>
            <ul className="mt-4 space-y-3 text-sm text-slate-700">
              <li>
                <strong>Workspace isolation:</strong> invoices, clients, and reminders stay inside this
                Tagado workspace only.
              </li>
              <li>
                <strong>Human approval:</strong> Claude can draft, but reminders are not sent until an
                owner or operator approves them.
              </li>
              <li>
                <strong>Client links:</strong> payment pages use a private link — share only with the right
                people.
              </li>
              <li>
                <strong>Payment confirmation:</strong> “I’ve paid” is a claim until someone confirms the bank
                credit.
              </li>
              <li>
                <strong>No AI keys in Tagado:</strong> thinking stays in Claude; Tagado stores and runs the
                workflow.
              </li>
            </ul>
          </article>

          <article className="rounded-2xl border border-[var(--line)] bg-[var(--card)] p-5 shadow-sm">
            <h2 className="text-lg font-semibold">Access controls</h2>
            <p className="mt-1 text-sm text-slate-600">
              Rotate the Claude connection link if it may have been shared outside your team.
            </p>
            <button
              type="button"
              onClick={() => void handleRegenerate()}
              disabled={busy}
              className="mt-4 rounded-lg border border-[var(--line)] px-3 py-2 text-sm font-medium"
            >
              Rotate Claude connection link
            </button>
          </article>

          {settings.is_demo ? (
            <article className="rounded-2xl border border-amber-200 bg-amber-50/80 p-5">
              <h2 className="text-lg font-semibold">Review workspace</h2>
              <p className="mt-1 text-sm text-slate-700">
                Restore the original sample clients and invoices used for product review.
              </p>
              <button
                type="button"
                onClick={() => void handleReset()}
                disabled={busy}
                className="mt-4 rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm font-medium"
              >
                Reset sample data
              </button>
            </article>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  hint,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  hint?: string;
}) {
  return (
    <label className="block text-sm font-medium">
      {label}
      {hint ? <span className="mt-1 block text-xs font-normal text-slate-500">{hint}</span> : null}
      <input
        className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 outline-none focus:border-[var(--accent)]"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function SaveButton({ busy, label = "Save changes" }: { busy: boolean; label?: string }) {
  return (
    <button
      type="submit"
      disabled={busy}
      className="rounded-lg bg-[var(--ink)] px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60"
    >
      {busy ? "Saving…" : label}
    </button>
  );
}
