import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { type InvoiceSummary, fetchDashboard } from "@/api/client";
import { StatusChip } from "@/components/StatusChip";
import { formatDate } from "@/lib/labels";

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

export function Invoices() {
  const navigate = useNavigate();
  const [invoices, setInvoices] = useState<InvoiceSummary[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchDashboard()
      .then((data) => {
        if (cancelled) return;
        setInvoices(data.invoices);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load invoices");
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
    return <p className="text-sm text-slate-500">Loading invoices…</p>;
  }

  if (error) {
    return <p className="text-sm text-rose-700">{error}</p>;
  }

  return (
    <div className="space-y-6">
      <section>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--accent)]">
          Workspace
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Invoices</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-600">
          Every invoice, its status, and when the next reminder is due.
        </p>
      </section>

      <section className="rounded-2xl border border-[var(--line)] bg-[var(--card)] p-5 shadow-sm">
        <div className="mb-4 flex flex-wrap gap-2">
          {FILTERS.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setFilter(item.key)}
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                filter === item.key
                  ? "bg-[var(--ink)] text-white"
                  : "bg-[var(--accent-soft)] text-slate-700 hover:bg-emerald-100"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {visible.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[var(--line)] bg-[var(--paper)] px-5 py-10 text-center">
            <p className="font-medium">No invoices in this view yet</p>
            <p className="mx-auto mt-2 max-w-md text-sm text-slate-600">
              In Claude, say: “Track my invoice to Kalpataru Retail for ₹50,000 due 15 Dec.” Then
              approve the plan here.
            </p>
            <Link
              to="/settings/claude"
              className="mt-4 inline-block text-sm font-medium text-[var(--accent)]"
            >
              Connect Claude
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
                    className="cursor-pointer border-b border-[var(--line)]/70 hover:bg-[var(--accent-soft)]/60"
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
