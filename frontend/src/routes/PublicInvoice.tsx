import { FormEvent, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { formatDate } from "@/lib/labels";

interface PublicInvoiceData {
  business_name: string;
  reply_to_email: string | null;
  invoice_number: string;
  description: string | null;
  amount_display: string;
  outstanding_display: string;
  outstanding_inr: number;
  due_date: string;
  status: string;
  status_line: string;
  invoice_url: string | null;
  can_respond: boolean;
  bank: {
    account_name: string;
    account_number: string;
    ifsc: string;
  } | null;
  upi_available: boolean;
  reported_paid_on: string | null;
  promise_date: string | null;
  issue_reason: string | null;
}

type ResponseMode = "paid" | "scheduled" | "need" | "problem" | null;

export function PublicInvoice() {
  const { token } = useParams<{ token: string }>();
  const [data, setData] = useState<PublicInvoiceData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [mode, setMode] = useState<ResponseMode>(null);
  const [busy, setBusy] = useState(false);

  async function load(): Promise<void> {
    if (!token) return;
    const response = await fetch(`/api/public/invoices/${token}`);
    if (!response.ok) {
      throw new Error(response.status === 404 ? "This payment link is invalid or expired." : "Could not load request");
    }
    setData((await response.json()) as PublicInvoiceData);
  }

  useEffect(() => {
    load().catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load request"));
  }, [token]);

  const pageUrl = useMemo(() => window.location.href, []);

  async function copy(text: string, label: string): Promise<void> {
    await navigator.clipboard.writeText(text);
    setNotice(`${label} copied.`);
  }

  async function submitResponse(body: Record<string, unknown>): Promise<void> {
    if (!token) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(`/api/public/invoices/${token}/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = (await response.json()) as PublicInvoiceData & { detail?: string };
      if (!response.ok) {
        throw new Error(payload.detail || "Could not submit your response");
      }
      setData(payload);
      setMode(null);
      setNotice("Thanks — your response was shared with the business.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not submit your response");
    } finally {
      setBusy(false);
    }
  }

  if (!data && !error) {
    return (
      <main className="mx-auto flex min-h-screen max-w-lg items-center justify-center px-4 text-sm text-slate-500">
        Loading payment request…
      </main>
    );
  }

  if (!data) {
    return (
      <main className="mx-auto flex min-h-screen max-w-lg items-center justify-center px-4 text-center">
        <div>
          <h1 className="text-xl font-semibold">Link not found</h1>
          <p className="mt-2 text-sm text-slate-600">{error}</p>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto min-h-screen w-full max-w-lg px-4 py-8">
      <p className="text-xs font-medium uppercase tracking-[0.16em] text-[var(--accent)]">Payment request</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">from {data.business_name}</h1>
      <p className="mt-1 text-sm text-slate-600">
        Review the invoice, pay using the details below, and tell them what happened next.
      </p>

      <section className="mt-6 rounded-2xl border border-[var(--line)] bg-white p-4 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold">{data.invoice_number}</p>
            <p className="mt-1 text-sm text-slate-600">{data.description || "Invoice payment"}</p>
          </div>
          <p className="text-lg font-semibold">{data.outstanding_display}</p>
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Due</dt>
            <dd className="mt-1 font-medium">{formatDate(data.due_date)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Status</dt>
            <dd className="mt-1 font-medium">{data.status_line}</dd>
          </div>
        </dl>
        {data.invoice_url ? (
          <a
            href={data.invoice_url}
            target="_blank"
            rel="noreferrer"
            className="mt-4 inline-block text-sm font-medium text-[var(--accent)]"
          >
            View invoice
          </a>
        ) : null}
      </section>

      {error ? <p className="mt-4 text-sm text-rose-700">{error}</p> : null}
      {notice ? <p className="mt-4 text-sm text-emerald-700">{notice}</p> : null}

      {!data.can_respond ? (
        <section className="mt-6 rounded-2xl border border-[var(--line)] bg-emerald-50/80 p-4">
          <h2 className="text-lg font-semibold">Current status</h2>
          <p className="mt-2 text-sm text-slate-700">{data.status_line}</p>
          {data.status === "paid" ? (
            <p className="mt-2 text-sm text-slate-600">No further action is needed from you.</p>
          ) : null}
        </section>
      ) : (
        <>
          <section className="mt-6 rounded-2xl border border-[var(--line)] bg-white p-4 shadow-sm">
            <h2 className="text-lg font-semibold">How to pay</h2>
            <p className="mt-1 text-sm text-slate-600">
              Use these details and quote {data.invoice_number} as the payment reference.
            </p>

            {data.bank ? (
              <div className="mt-4 space-y-3 text-sm">
                <CopyRow label="Account name" value={data.bank.account_name} onCopy={copy} />
                <CopyRow label="Account number" value={data.bank.account_number} onCopy={copy} />
                <CopyRow label="IFSC" value={data.bank.ifsc} onCopy={copy} />
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-600">
                Payment details will be shared by {data.business_name}.
              </p>
            )}

            {data.upi_available && token ? (
              <div className="mt-5 rounded-xl bg-[var(--paper)] p-3 text-center">
                <p className="text-sm font-medium">UPI QR</p>
                <p className="mt-1 text-xs text-slate-500">For amounts up to ₹1,00,000</p>
                <img
                  className="mx-auto mt-3 h-44 w-44 rounded-lg bg-white p-2"
                  src={`/api/public/invoices/${token}/upi-qr.png`}
                  alt="UPI QR code"
                />
              </div>
            ) : null}
          </section>

          <section className="mt-6 rounded-2xl border border-[var(--line)] bg-white p-4 shadow-sm">
            <h2 className="text-lg font-semibold">Respond</h2>
            <p className="mt-1 text-sm text-slate-600">
              Tell {data.business_name} where things stand. This pauses reminders automatically.
            </p>

            <div className="mt-4 grid gap-2">
              <ResponseButton active={mode === "paid"} onClick={() => setMode("paid")}>
                I’ve paid
              </ResponseButton>
              <ResponseButton active={mode === "scheduled"} onClick={() => setMode("scheduled")}>
                Payment is scheduled
              </ResponseButton>
              <ResponseButton active={mode === "need"} onClick={() => setMode("need")}>
                I need something
              </ResponseButton>
              <ResponseButton active={mode === "problem"} onClick={() => setMode("problem")}>
                There’s a problem
              </ResponseButton>
              <button
                type="button"
                className="rounded-xl border border-[var(--line)] px-4 py-3 text-left text-sm font-medium"
                onClick={() => void copy(pageUrl, "Link")}
              >
                Share with accounts team
              </button>
            </div>

            {mode === "paid" ? (
              <PaidForm
                defaultAmount={data.outstanding_inr}
                busy={busy}
                onSubmit={(values) =>
                  void submitResponse({
                    type: "paid",
                    amount_inr: values.amount,
                    paid_on: values.paidOn,
                    reference: values.reference || null,
                  })
                }
              />
            ) : null}
            {mode === "scheduled" ? (
              <ScheduledForm
                busy={busy}
                onSubmit={(promiseDate) =>
                  void submitResponse({ type: "scheduled", promise_date: promiseDate })
                }
              />
            ) : null}
            {mode === "need" ? (
              <IssueForm
                title="What do you need?"
                options={["Invoice copy", "PO number missing", "GSTIN correction"]}
                busy={busy}
                onSubmit={(reason, note) =>
                  void submitResponse({ type: "need", reason, note: note || null })
                }
              />
            ) : null}
            {mode === "problem" ? (
              <IssueForm
                title="What’s the problem?"
                options={["Amount looks wrong", "Work incomplete", "Other"]}
                busy={busy}
                onSubmit={(reason, note) =>
                  void submitResponse({ type: "problem", reason, note: note || null })
                }
              />
            ) : null}
          </section>
        </>
      )}

      <footer className="mt-8 space-y-1 text-center text-xs text-slate-500">
        <p>
          Questions? Reply to the email or write to {data.reply_to_email || data.business_name}.
        </p>
        <p>Sent via Tagado</p>
      </footer>
    </main>
  );
}

function CopyRow({
  label,
  value,
  onCopy,
}: {
  label: string;
  value: string;
  onCopy: (value: string, label: string) => Promise<void>;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-[var(--line)] px-3 py-2">
      <div>
        <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
        <p className="font-medium">{value}</p>
      </div>
      <button
        type="button"
        className="rounded-lg bg-[var(--ink)] px-3 py-1.5 text-xs font-medium text-white"
        onClick={() => void onCopy(value, label)}
      >
        Copy
      </button>
    </div>
  );
}

function ResponseButton({
  children,
  onClick,
  active,
}: {
  children: string;
  onClick: () => void;
  active: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-xl px-4 py-3 text-left text-sm font-medium ${
        active
          ? "bg-[var(--ink)] text-white"
          : "border border-[var(--line)] bg-[var(--paper)]/60 text-[var(--ink)]"
      }`}
    >
      {children}
    </button>
  );
}

function PaidForm({
  defaultAmount,
  busy,
  onSubmit,
}: {
  defaultAmount: number;
  busy: boolean;
  onSubmit: (values: { amount: number; paidOn: string; reference: string }) => void;
}) {
  const [amount, setAmount] = useState(String(defaultAmount));
  const [paidOn, setPaidOn] = useState(new Date().toISOString().slice(0, 10));
  const [reference, setReference] = useState("");

  function handleSubmit(event: FormEvent): void {
    event.preventDefault();
    onSubmit({ amount: Number(amount), paidOn, reference });
  }

  return (
    <form onSubmit={handleSubmit} className="mt-4 space-y-3 rounded-xl bg-[var(--paper)]/70 p-3">
      <label className="block text-sm">
        Amount paid (₹)
        <input
          className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2"
          type="number"
          min="1"
          step="0.01"
          required
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
        />
      </label>
      <label className="block text-sm">
        Payment date
        <input
          className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2"
          type="date"
          required
          value={paidOn}
          onChange={(event) => setPaidOn(event.target.value)}
        />
      </label>
      <label className="block text-sm">
        UTR / reference
        <input
          className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2"
          value={reference}
          onChange={(event) => setReference(event.target.value)}
          placeholder="Optional but helpful"
        />
      </label>
      <button
        type="submit"
        disabled={busy}
        className="w-full rounded-lg bg-[var(--accent)] px-3 py-2.5 text-sm font-medium text-white disabled:opacity-60"
      >
        {busy ? "Submitting…" : "Submit payment report"}
      </button>
    </form>
  );
}

function ScheduledForm({
  busy,
  onSubmit,
}: {
  busy: boolean;
  onSubmit: (promiseDate: string) => void;
}) {
  const [promiseDate, setPromiseDate] = useState("");

  function handleSubmit(event: FormEvent): void {
    event.preventDefault();
    onSubmit(promiseDate);
  }

  return (
    <form onSubmit={handleSubmit} className="mt-4 space-y-3 rounded-xl bg-[var(--paper)]/70 p-3">
      <label className="block text-sm">
        Expected payment date
        <input
          className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2"
          type="date"
          required
          value={promiseDate}
          onChange={(event) => setPromiseDate(event.target.value)}
        />
      </label>
      <button
        type="submit"
        disabled={busy}
        className="w-full rounded-lg bg-[var(--accent)] px-3 py-2.5 text-sm font-medium text-white disabled:opacity-60"
      >
        {busy ? "Submitting…" : "Share schedule"}
      </button>
    </form>
  );
}

function IssueForm({
  title,
  options,
  busy,
  onSubmit,
}: {
  title: string;
  options: string[];
  busy: boolean;
  onSubmit: (reason: string, note: string) => void;
}) {
  const [reason, setReason] = useState(options[0] ?? "");
  const [note, setNote] = useState("");

  function handleSubmit(event: FormEvent): void {
    event.preventDefault();
    onSubmit(reason, note);
  }

  return (
    <form onSubmit={handleSubmit} className="mt-4 space-y-3 rounded-xl bg-[var(--paper)]/70 p-3">
      <label className="block text-sm">
        {title}
        <select
          className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        >
          {options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
      <label className="block text-sm">
        Short note
        <textarea
          className="mt-1 min-h-20 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="Optional details"
        />
      </label>
      <button
        type="submit"
        disabled={busy}
        className="w-full rounded-lg bg-[var(--accent)] px-3 py-2.5 text-sm font-medium text-white disabled:opacity-60"
      >
        {busy ? "Submitting…" : "Send to business"}
      </button>
    </form>
  );
}
