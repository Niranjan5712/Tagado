import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  type AttentionItem,
  type DashboardTotals,
  type WorkspaceSettings,
  fetchDashboard,
  fetchSettings,
} from "@/api/client";
import { StatCard } from "@/components/StatCard";
import { attentionTitle, relativeTime } from "@/lib/labels";

function attentionActionLabel(type: string): string {
  if (type === "payment_reported") return "Verify";
  if (type === "issue_raised") return "Resolve";
  if (type === "plan_awaiting_approval") return "Review";
  if (type === "promise_broken") return "Decide";
  return "Open";
}

export function Home() {
  const navigate = useNavigate();
  const [totals, setTotals] = useState<DashboardTotals | null>(null);
  const [attention, setAttention] = useState<AttentionItem[]>([]);
  const [settings, setSettings] = useState<WorkspaceSettings | null>(null);
  const [invoiceCount, setInvoiceCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchDashboard(), fetchSettings()])
      .then(([dashboard, workspace]) => {
        if (cancelled) return;
        setTotals(dashboard.totals);
        setAttention(dashboard.attention);
        setInvoiceCount(dashboard.invoices.length);
        setSettings(workspace);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load workspace");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <p className="text-sm text-slate-500">Opening your workspace…</p>;
  }

  if (error) {
    return <p className="text-sm text-rose-700">{error}</p>;
  }

  const businessName = settings?.business_name || "Your workspace";

  return (
    <div className="space-y-8">
      <section className="rounded-2xl border border-[var(--line)] bg-[var(--card)] p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--accent)]">
          Workspace
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">{businessName}</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-600">
          This is your Tagado workspace. Track receivables, approve Claude’s follow-ups, and confirm
          payments — without leaving control of what gets sent.
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          <Link
            to="/invoices"
            className="rounded-lg bg-[var(--accent)] px-4 py-2.5 text-sm font-medium text-white"
          >
            Open invoices
          </Link>
          <Link
            to="/settings/claude"
            className="rounded-lg border border-[var(--line)] bg-white px-4 py-2.5 text-sm font-medium"
          >
            Connect Claude
          </Link>
          <Link
            to="/settings/branding"
            className="rounded-lg border border-[var(--line)] bg-white px-4 py-2.5 text-sm font-medium"
          >
            Branding & identity
          </Link>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <StatCard
          title="Outstanding"
          description="Total unpaid amount across invoices still open."
          value={totals?.outstanding_display ?? "₹0"}
          meta={`${totals?.outstanding_count ?? 0} invoices`}
        />
        <StatCard
          title="Overdue"
          description="Past the due date and still unpaid."
          value={totals?.overdue_display ?? "₹0"}
          meta={`${totals?.overdue_count ?? 0} invoices`}
          emphasize={(totals?.overdue_count ?? 0) > 0}
        />
        <StatCard
          title="Due in 7 days"
          description="Coming due this week — good to watch early."
          value={totals?.due_soon_display ?? "₹0"}
          meta={`${totals?.due_soon_count ?? 0} invoices`}
        />
        <StatCard
          title="Promised"
          description="Clients who gave a payment date."
          value={totals?.promised_display ?? "₹0"}
          meta={`${totals?.promised_count ?? 0} invoices`}
        />
        <StatCard
          title="Needs attention"
          description="Waiting for your confirmation or decision."
          value={String(totals?.needs_attention_count ?? 0)}
          meta={`${totals?.payment_reported_count ?? 0} to verify · ${totals?.open_issues_count ?? 0} open issues · ${totals?.awaiting_approval_count ?? 0} awaiting approval · ${totals?.held_reminders_count ?? 0} on hold`}
          emphasize={(totals?.needs_attention_count ?? 0) > 0}
        />
        <StatCard
          title="Collected (30 days)"
          description="Payments you confirmed in the last month."
          value={totals?.collected_30d_display ?? "₹0"}
          meta="Only bank-confirmed amounts"
        />
      </section>

      {attention.length > 0 ? (
        <section className="rounded-2xl border border-[var(--line)] bg-[var(--card)] p-5 shadow-sm">
          <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold">Needs your attention</h2>
              <p className="mt-1 text-sm text-slate-600">
                Start here. These invoices are blocked until you respond.
              </p>
            </div>
            <Link to="/invoices" className="text-sm font-medium text-[var(--accent)]">
              View all invoices
            </Link>
          </div>
          <ul className="divide-y divide-[var(--line)]">
            {attention.map((item) => (
              <li
                key={`${item.type}-${item.invoice_id}`}
                className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="text-sm font-medium text-[var(--ink)]">
                    {attentionTitle(item.type)} · {item.client_name}
                  </p>
                  <p className="mt-1 text-sm text-slate-600">
                    {item.invoice_number} — {item.summary}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">{relativeTime(item.occurred_at)}</p>
                </div>
                <button
                  type="button"
                  onClick={() => navigate(`/invoices/${item.invoice_id}`)}
                  className="rounded-lg bg-[var(--ink)] px-3 py-2 text-sm font-medium text-white"
                >
                  {attentionActionLabel(item.type)}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <section className="rounded-2xl border border-dashed border-[var(--line)] bg-[var(--paper)] px-5 py-8 text-center">
          <p className="font-medium">You’re clear for now</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-slate-600">
            {invoiceCount > 0
              ? "Nothing needs a decision. Open invoices to review schedules and status."
              : "No invoices yet. In Claude, say: “Track my invoice to Kalpataru Retail for ₹50,000 due 15 Dec.”"}
          </p>
          <Link
            to={invoiceCount > 0 ? "/invoices" : "/settings/claude"}
            className="mt-4 inline-block text-sm font-medium text-[var(--accent)]"
          >
            {invoiceCount > 0 ? "Open invoices" : "Connect Claude"}
          </Link>
        </section>
      )}

      <section className="grid gap-4 sm:grid-cols-3">
        <Shortcut
          title="Invoices"
          description="Filter open, overdue, promised, and paid invoices."
          to="/invoices"
        />
        <Shortcut
          title="Payment details"
          description="Bank, UPI, and MSME details shown to clients."
          to="/settings/payments"
        />
        <Shortcut
          title="Data & access"
          description="Governance rules and review-workspace controls."
          to="/settings/data"
        />
      </section>
    </div>
  );
}

function Shortcut({
  title,
  description,
  to,
}: {
  title: string;
  description: string;
  to: string;
}) {
  return (
    <Link
      to={to}
      className="rounded-2xl border border-[var(--line)] bg-[var(--card)] p-4 shadow-sm transition hover:border-[var(--accent)] hover:bg-[var(--accent-soft)]/40"
    >
      <p className="text-sm font-semibold">{title}</p>
      <p className="mt-1 text-xs leading-relaxed text-slate-500">{description}</p>
    </Link>
  );
}
