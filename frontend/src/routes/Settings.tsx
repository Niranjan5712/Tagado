import { FormEvent, useEffect, useState } from "react";

import {
  type WorkspaceSettings,
  fetchSettings,
  regenerateClaudeLink,
  resetSampleData,
  saveSettings,
} from "@/api/client";

export function Settings() {
  const [settings, setSettings] = useState<WorkspaceSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchSettings()
      .then(setSettings)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load settings"));
  }, []);

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
      const refreshed = await fetchSettings();
      setSettings(refreshed);
      setMessage(result.summary);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reset sample data");
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

  return (
    <div className="space-y-8">
      <section>
        <h1 className="text-3xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-slate-600">
          Your business details, payment information, and how Claude connects to Tagado.
        </p>
      </section>

      {error ? <p className="text-sm text-rose-700">{error}</p> : null}
      {message ? <p className="text-sm text-emerald-700">{message}</p> : null}

      <form onSubmit={handleSave} className="space-y-6 rounded-2xl border border-[var(--line)] bg-white/90 p-5 shadow-sm">
        <div>
          <h2 className="text-lg font-semibold">Business profile</h2>
          <p className="mt-1 text-sm text-slate-600">
            Shown on reminders and on the page your client opens to respond.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Business name"
            value={settings.business_name}
            onChange={(value) => setSettings({ ...settings, business_name: value })}
          />
          <Field
            label="Sender name"
            value={settings.sender_name}
            onChange={(value) => setSettings({ ...settings, sender_name: value })}
          />
          <Field
            label="Reply-to email"
            value={settings.reply_to_email ?? ""}
            onChange={(value) => setSettings({ ...settings, reply_to_email: value })}
          />
        </div>

        <div>
          <h2 className="text-lg font-semibold">Bank details for clients</h2>
          <p className="mt-1 text-sm text-slate-600">
            Added automatically to reminder emails and the client payment page.
          </p>
        </div>
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
            value={settings.upi_id ?? ""}
            onChange={(value) => setSettings({ ...settings, upi_id: value })}
          />
          <Field
            label="Udyam number (optional)"
            value={settings.udyam_number ?? ""}
            onChange={(value) => setSettings({ ...settings, udyam_number: value })}
          />
        </div>

        {settings.msme_note_preview ? (
          <div className="rounded-xl bg-emerald-50/80 p-4 text-sm text-emerald-950">
            <p className="font-medium">MSME note preview</p>
            <p className="mt-1 text-xs text-emerald-800">Template wording — pending CA review.</p>
            <p className="mt-2 leading-relaxed">{settings.msme_note_preview}</p>
          </div>
        ) : null}

        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-[var(--ink)] px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60"
        >
          {busy ? "Saving…" : "Save settings"}
        </button>
      </form>

      <section className="rounded-2xl border border-[var(--line)] bg-white/90 p-5 shadow-sm">
        <h2 className="text-lg font-semibold">Connect Claude</h2>
        <p className="mt-1 text-sm text-slate-600">
          Let Claude create and update invoices in Tagado using your account. Nothing is sent until
          you approve it here.
        </p>
        <div className="mt-4 rounded-xl border border-[var(--line)] bg-[var(--paper)]/50 p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Connection link</p>
          <p className="mt-2 break-all text-sm text-slate-800">{settings.claude_connection_url}</p>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={copyLink}
            className="rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white"
          >
            Copy link
          </button>
          <button
            type="button"
            onClick={handleRegenerate}
            disabled={busy}
            className="rounded-lg border border-[var(--line)] px-3 py-2 text-sm font-medium"
          >
            Create new link
          </button>
        </div>
        <ol className="mt-5 list-decimal space-y-2 pl-5 text-sm text-slate-700">
          <li>In Claude, open Settings → Connectors.</li>
          <li>Choose Add custom connector, name it Tagado, and paste the link above.</li>
          <li>Connect, then ask Claude: “What can Tagado do?”</li>
        </ol>
      </section>

      {settings.is_demo ? (
        <section className="rounded-2xl border border-amber-200 bg-amber-50/70 p-5">
          <h2 className="text-lg font-semibold">Sample data</h2>
          <p className="mt-1 text-sm text-slate-700">
            Restore the review workspace to the original sample clients and invoices.
          </p>
          <button
            type="button"
            onClick={handleReset}
            disabled={busy}
            className="mt-4 rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm font-medium"
          >
            Reset sample data
          </button>
        </section>
      ) : null}
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block text-sm font-medium">
      {label}
      <input
        className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 outline-none focus:border-[var(--accent)]"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
