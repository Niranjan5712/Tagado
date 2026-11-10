import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  type AttentionItem,
  type DashboardTotals,
  type InvoiceSummary,
  fetchDashboard,
} from "@/api/client";
import { StatusChip } from "@/components/StatusChip";
import { attentionTitle, formatDate, relativeTime } from "@/lib/labels";

const FILTERS = [
  { key: "all", label: "All" },
  { key: "open", label: "Open" },
  { key: "overdue", label: "Overdue" },
  { key: "promised", label: "Promised" },
  { key: "issues", label: "Issues" },
  { key: "paid", label: "Paid" },
] as const;

function matchesFilter(invoice: InvoiceSummary, filter: string): boolean {
  if (filter === "all") return true;
  if (filter === "open") return invoice.status === "open";
  if (filter === "overdue") return invoice.days_overdue > 0;
  if (filter === "promised") return invoice.status === "promised";
  if (filter === "issues") return invoice.status === "issue_raised";
  if (filter === "paid") return invoice.status === "paid";
  return true;
}

function attentionActionLabel(type: string): string {
  if (type === "payment_reported") return "Verify";
  if (type === "issue_raised") return "Resolve";
  if (type === "plan_awaiting_approval") return "Review";
  if (type === "promise_broken") return "Decide";
  return "Open";
}

export function Dashboard() {
  const navigate = useNavigate();
  const [totals, setTotals] = useState<DashboardTotals | null>(null);
  const [attention, setAttention] = useState<AttentionItem[]>([]);
  const [invoices, setInvoices] = useState<InvoiceSummary[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchDashboard()
      .then((data) => {
        if (cancelled) return;
        setTotals(data.totals);
        setAttention(data.attention);
        setInvoices(data.invoices);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load dashboard");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const visible = useMemo(
    () => invoices.filter((invoice) => matchesFilter(invoice, filter)),
    [invoices, filter],
  );

  if (loading) {
    return <p className="text-sm text-slate-500">Loading your receivables…</p>;
  }

  if (error) {
    return <p className="text-sm text-rose-700">{error}</p>;
  }

  return (
    <div className="space-y-8">
      <section>
        <h1 className="text-3xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-600">
          A live view of money owed to you, what needs action today, and upcoming reminders.
        </p>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          title="Outstanding"
          description="Total unpaid amount across open invoices."
          value={totals?.outstanding_display ?? "₹0"}
          meta={`${totals?.outstanding_count ?? 0} invoices`}
        />
        <StatCard
          title="Overdue"
          description="Past due date and still waiting for payment."
          value={totals?.overdue_display ?? "₹0"}
          meta={`${totals?.overdue_count ?? 0} invoices`}
          emphasize={(totals?.overdue_count ?? 0) > 0}
        />
        <StatCard
          title="Needs attention"
          description="Items waiting for your decision or confirmation."
          value={String(totals?.needs_attention_count ?? 0)}
          meta="Act on these first"
          emphasize={(totals?.needs_attention_count ?? 0) > 0}
        />
        <StatCard
          title="Collected (30 days)"
          description="Payments you confirmed in the last month."
          value={totals?.collected_30d_display ?? "₹0"}
          meta="Bank-confirmed only"
        />
      </section>

      {attention.length > 0 ? (
        <section className="rounded-2xl border border-[var(--line)] bg-white/90 p-5 shadow-sm">
          <div className="mb-4">
            <h2 className="text-lg font-semibold">Needs your attention</h2>
            <p className="mt-1 text-sm text-slate-600">
              Start here. These are the invoices that are blocked until you respond.
            </p>
          </div>
          <ul className="divide-y divide-[var(--line)]">
            {attention.map((item) => (
              <li key={`${item.type}-${item.invoice_id}`} className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
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
      ) : null}

      <section className="rounded-2xl border border-[var(--line)] bg-white/90 p-5 shadow-sm">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold">Invoices</h2>
            <p className="mt-1 text-sm text-slate-600">
              Track every invoice, its payment status, and when the next reminder goes out.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {FILTERS.map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setFilter(item.key)}
                className={`rounded-full px-3 py-1 text-xs font-medium ${
                  filter === item.key
                    ? "bg-[var(--ink)] text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        {visible.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[var(--line)] bg-[var(--paper)]/60 px-5 py-10 text-center">
            <p className="font-medium">No invoices in this view yet</p>
            <p className="mx-auto mt-2 max-w-md text-sm text-slate-600">
              In Claude, say: “Track my invoice to Kalpataru Retail for ₹50,000 due 15 Dec.” Then
              approve the plan here.
            </p>
            <Link to="/settings" className="mt-4 inline-block text-sm font-medium text-[var(--accent)]">
              Connect Claude in Settings
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-[var(--line)] text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="py-2 pr-3 font-medium">Client</th>
                  <th className="py-2 pr-3 font-medium">Invoice</th>
                  <th className="py-2 pr-3 font-medium">Amount</th>
                  <th className="py-2 pr-3 font-medium">Due</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 font-medium">Next reminder</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((invoice) => (
                  <tr
                    key={invoice.id}
                    className="cursor-pointer border-b border-[var(--line)]/70 hover:bg-emerald-50/40"
                    onClick={() => navigate(`/invoices/${invoice.id}`)}
                  >
                    <td className="py-3 pr-3 font-medium">{invoice.client_name}</td>
                    <td className="py-3 pr-3">{invoice.invoice_number}</td>
                    <td className="py-3 pr-3">{invoice.outstanding_display}</td>
                    <td className="py-3 pr-3">
                      <div>{formatDate(invoice.due_date)}</div>
                      {invoice.days_overdue > 0 ? (
                        <div className="text-xs font-medium text-rose-700">
                          {invoice.days_overdue} days overdue
                        </div>
                      ) : null}
                    </td>
                    <td className="py-3 pr-3">
                      <div className="flex flex-col gap-1">
                        <StatusChip value={invoice.status} />
                        <StatusChip value={invoice.plan_status} kind="plan" />
                      </div>
                    </td>
                    <td className="py-3">
                      {invoice.next_reminder === "Held"
                        ? "On hold"
                        : invoice.next_reminder
                          ? formatDate(invoice.next_reminder)
                          : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function StatCard({
  title,
  description,
  value,
  meta,
  emphasize = false,
}: {
  title: string;
  description: string;
  value: string;
  meta: string;
  emphasize?: boolean;
}) {
  return (
    <article
      className={`rounded-2xl border p-4 shadow-sm ${
        emphasize
          ? "border-rose-200 bg-rose-50/70"
          : "border-[var(--line)] bg-white/90"
      }`}
    >
      <h3 className="text-sm font-semibold text-[var(--ink)]">{title}</h3>
      <p className="mt-1 text-xs leading-relaxed text-slate-500">{description}</p>
      <p className="mt-3 text-2xl font-semibold tracking-tight">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{meta}</p>
    </article>
  );
}
