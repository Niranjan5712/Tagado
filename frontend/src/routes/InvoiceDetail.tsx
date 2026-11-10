import { useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import {
  type InvoiceDetail as InvoiceDetailType,
  type InvoiceMessage,
  deleteMessage,
  fetchInvoice,
  patchMessage,
  postInvoiceAction,
  previewMessage,
  sendMessageNow,
} from "@/api/client";
import { StatusChip } from "@/components/StatusChip";
import {
  eventLabel,
  formatDate,
  formatDateTime,
  messageStatusLabel,
} from "@/lib/labels";

export function InvoiceDetail() {
  const { id } = useParams<{ id: string }>();
  const [invoice, setInvoice] = useState<InvoiceDetailType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<{ subject: string; html: string; to: string[] } | null>(
    null,
  );

  async function reload(): Promise<void> {
    if (!id) return;
    const data = await fetchInvoice(id);
    setInvoice(data);
  }

  useEffect(() => {
    if (!id) return;
    reload().catch((err: unknown) =>
      setError(err instanceof Error ? err.message : "Could not load invoice"),
    );
  }, [id]);

  async function runAction(
    action:
      | "approve"
      | "pause"
      | "resume"
      | "cancel"
      | "confirm-payment"
      | "reject-payment"
      | "resolve-issue",
  ): Promise<void> {
    if (!invoice) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await postInvoiceAction(invoice.id, action);
      setInvoice(updated);
      setNotice("Saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  if (!invoice && !error) {
    return <p className="text-sm text-slate-500">Loading invoice…</p>;
  }
  if (!invoice) {
    return <p className="text-sm text-rose-700">{error}</p>;
  }

  const mains = invoice.messages.filter((message) => message.kind === "main");
  const checkin = invoice.messages.find((message) => message.kind === "promise_checkin");

  return (
    <div className="space-y-6">
      <div>
        <Link to="/" className="text-sm font-medium text-[var(--accent)]">
          ← Back to dashboard
        </Link>
        <div className="mt-3 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">
              {invoice.invoice_number}
            </h1>
            <p className="mt-1 text-sm text-slate-600">
              Review the follow-up plan, handle client replies, and confirm when money arrives.
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <StatusChip value={invoice.status} />
              <StatusChip value={invoice.plan_status} kind="plan" />
              <span className="rounded-full border border-teal-200 bg-teal-50 px-2.5 py-0.5 text-xs font-medium text-teal-900">
                Drafted with Claude
              </span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {invoice.plan_status === "draft" ? (
              <ActionButton disabled={busy} onClick={() => runAction("approve")}>
                Approve plan
              </ActionButton>
            ) : null}
            {invoice.plan_status === "active" ? (
              <ActionButton disabled={busy} onClick={() => runAction("pause")} secondary>
                Pause
              </ActionButton>
            ) : null}
            {invoice.plan_status === "paused" && invoice.status !== "issue_raised" ? (
              <ActionButton disabled={busy} onClick={() => runAction("resume")}>
                Resume
              </ActionButton>
            ) : null}
            {invoice.status === "payment_reported" ? (
              <>
                <ActionButton disabled={busy} onClick={() => runAction("confirm-payment")}>
                  Confirm payment
                </ActionButton>
                <ActionButton disabled={busy} onClick={() => runAction("reject-payment")} secondary>
                  Not received
                </ActionButton>
              </>
            ) : null}
            {invoice.status === "issue_raised" ? (
              <ActionButton disabled={busy} onClick={() => runAction("resolve-issue")}>
                Resolve & resume
              </ActionButton>
            ) : null}
            {invoice.status !== "paid" && invoice.status !== "cancelled" ? (
              <ActionButton disabled={busy} onClick={() => runAction("cancel")} secondary>
                Cancel invoice
              </ActionButton>
            ) : null}
            <ActionButton
              secondary
              onClick={async () => {
                await navigator.clipboard.writeText(invoice.client_page_url);
                setNotice("Client page link copied.");
              }}
            >
              Copy client link
            </ActionButton>
            <a
              href={invoice.client_page_url}
              target="_blank"
              rel="noreferrer"
              className="rounded-lg border border-[var(--line)] px-3 py-2 text-sm font-medium"
            >
              Open client page
            </a>
          </div>
        </div>
      </div>

      {error ? <p className="text-sm text-rose-700">{error}</p> : null}
      {notice ? <p className="text-sm text-emerald-700">{notice}</p> : null}

      <section className="grid gap-4 rounded-2xl border border-[var(--line)] bg-white/90 p-5 shadow-sm sm:grid-cols-4">
        <Meta label="Client" value={invoice.client_name} />
        <Meta label="Outstanding" value={invoice.outstanding_display} />
        <Meta label="Due date" value={formatDate(invoice.due_date)} />
        <Meta
          label="Overdue"
          value={invoice.days_overdue > 0 ? `${invoice.days_overdue} days` : "On track"}
        />
      </section>

      {invoice.plan_status === "draft" ? (
        <div className="rounded-xl border border-orange-200 bg-orange-50 px-4 py-3 text-sm text-orange-950">
          Nothing has been sent yet. Review the messages below and approve when they look right.
        </div>
      ) : null}

      {(invoice.status === "payment_reported" ||
        invoice.status === "promised" ||
        invoice.status === "issue_raised") && (
        <section className="rounded-2xl border border-violet-200 bg-violet-50/70 p-5">
          <h2 className="text-lg font-semibold">Client response</h2>
          <p className="mt-1 text-sm text-slate-700">
            What the client told you from the payment page — take the next step here.
          </p>
          {invoice.status === "payment_reported" ? (
            <p className="mt-3 text-sm">
              Reported {invoice.reported_amount_display} on {formatDate(invoice.reported_paid_on)}{" "}
              {invoice.reported_reference ? `(ref ${invoice.reported_reference})` : ""}.
            </p>
          ) : null}
          {invoice.status === "promised" ? (
            <p className="mt-3 text-sm">
              Promised payment on {formatDate(invoice.promise_date)}
              {invoice.promise_count > 1 ? ` · promise #${invoice.promise_count}` : ""}.
            </p>
          ) : null}
          {invoice.status === "issue_raised" ? (
            <p className="mt-3 text-sm">
              {invoice.issue_reason}
              {invoice.issue_note ? ` — ${invoice.issue_note}` : ""}
            </p>
          ) : null}
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-[1.4fr_0.8fr]">
        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Follow-up plan</h2>
            <p className="mt-1 text-sm text-slate-600">
              The reminders Claude drafted. Edit freely, then approve before anything goes out.
            </p>
          </div>
          {mains.map((message, index) => (
            <MessageEditor
              key={message.id}
              message={message}
              index={index + 1}
              isLastMain={index === mains.length - 1}
              canToggleMsme={invoice.workspace_has_udyam}
              planStatus={invoice.plan_status}
              disabled={busy}
              onSaved={async (updated) => {
                setInvoice(updated);
                setNotice("Message updated.");
              }}
              onPreview={async () => {
                const data = await previewMessage(message.id);
                setPreview({ subject: data.subject, html: data.html, to: data.to });
              }}
              onSendNow={async () => {
                setBusy(true);
                try {
                  await sendMessageNow(message.id);
                  await reload();
                  setNotice("Reminder sent. Find it in Sent mail below.");
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Could not send");
                } finally {
                  setBusy(false);
                }
              }}
              onDelete={async () => {
                const updated = await deleteMessage(message.id);
                setInvoice(updated);
                setNotice("Message removed.");
              }}
            />
          ))}
          {checkin ? (
            <article className="rounded-2xl border border-dashed border-[var(--line)] bg-white/70 p-4">
              <p className="text-sm font-semibold">Promise check-in</p>
              <p className="mt-1 text-xs text-slate-500">
                Sent only if the client commits to a payment date.
              </p>
              <p className="mt-3 text-sm font-medium">{checkin.subject}</p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{checkin.body}</p>
              <div className="mt-3">
                <StatusChip value={checkin.status} kind="message" />
              </div>
            </article>
          ) : null}
        </section>

        <aside className="space-y-4">
          <section className="rounded-2xl border border-[var(--line)] bg-white/90 p-4 shadow-sm">
            <h2 className="text-lg font-semibold">Timeline</h2>
            <p className="mt-1 text-sm text-slate-600">A clear history of what happened on this invoice.</p>
            <ul className="mt-4 space-y-3">
              {invoice.events.map((event) => (
                <li key={event.id} className="border-l-2 border-teal-200 pl-3">
                  <p className="text-sm font-medium">{eventLabel(event.type)}</p>
                  <p className="text-xs text-slate-500">{formatDateTime(event.created_at)}</p>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-2xl border border-[var(--line)] bg-white/90 p-4 shadow-sm">
            <h2 className="text-lg font-semibold">Sent mail</h2>
            <p className="mt-1 text-sm text-slate-600">
              Reminders and notices Tagado prepared for this invoice.
            </p>
            {invoice.outbox.length === 0 ? (
              <p className="mt-4 text-sm text-slate-500">Nothing sent yet.</p>
            ) : (
              <ul className="mt-4 space-y-3">
                {invoice.outbox.map((item) => (
                  <li key={item.id} className="rounded-xl border border-[var(--line)] p-3">
                    <p className="text-sm font-medium">{item.subject}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      To {item.to.join(", ")} · {formatDateTime(item.created_at)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>

      {preview ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded-2xl bg-white p-5 shadow-xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold">Email preview</h3>
                <p className="mt-1 text-sm text-slate-600">Exactly how the reminder will look.</p>
              </div>
              <button type="button" className="text-sm" onClick={() => setPreview(null)}>
                Close
              </button>
            </div>
            <p className="mt-4 text-sm">
              <span className="text-slate-500">To:</span> {preview.to.join(", ")}
            </p>
            <p className="mt-1 text-sm font-medium">{preview.subject}</p>
            <div
              className="mt-4 overflow-hidden rounded-xl border border-[var(--line)]"
              dangerouslySetInnerHTML={{ __html: preview.html }}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold">{value}</p>
    </div>
  );
}

function ActionButton({
  children,
  onClick,
  disabled,
  secondary = false,
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  secondary?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`rounded-lg px-3 py-2 text-sm font-medium disabled:opacity-60 ${
        secondary
          ? "border border-[var(--line)] bg-white text-slate-800"
          : "bg-[var(--ink)] text-white"
      }`}
    >
      {children}
    </button>
  );
}

function MessageEditor({
  message,
  index,
  isLastMain,
  canToggleMsme,
  planStatus,
  disabled,
  onSaved,
  onPreview,
  onSendNow,
  onDelete,
}: {
  message: InvoiceMessage;
  index: number;
  isLastMain: boolean;
  canToggleMsme: boolean;
  planStatus: string;
  disabled: boolean;
  onSaved: (invoice: InvoiceDetailType) => Promise<void> | void;
  onPreview: () => Promise<void>;
  onSendNow: () => Promise<void>;
  onDelete: () => Promise<void>;
}) {
  const editable = ["draft", "scheduled", "held"].includes(message.status);
  const [subject, setSubject] = useState(message.subject);
  const [body, setBody] = useState(message.body);
  const [sendOn, setSendOn] = useState(message.send_on ?? "");
  const [msme, setMsme] = useState(message.include_msme_note);

  useEffect(() => {
    setSubject(message.subject);
    setBody(message.body);
    setSendOn(message.send_on ?? "");
    setMsme(message.include_msme_note);
  }, [message]);

  return (
    <article className="rounded-2xl border border-[var(--line)] bg-white/90 p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold">
            Reminder {index}
            <span className="ml-2 font-normal text-slate-500">· {message.tone}</span>
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {message.send_on ? `Send on ${formatDate(message.send_on)}` : "No send date yet"} ·{" "}
            {messageStatusLabel(message.status)}
          </p>
        </div>
        <StatusChip value={message.status} kind="message" />
      </div>

      {editable ? (
        <div className="mt-4 space-y-3">
          <input
            className="w-full rounded-lg border border-[var(--line)] px-3 py-2 text-sm"
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
          />
          <textarea
            className="min-h-28 w-full rounded-lg border border-[var(--line)] px-3 py-2 text-sm"
            value={body}
            onChange={(event) => setBody(event.target.value)}
          />
          <input
            type="date"
            className="rounded-lg border border-[var(--line)] px-3 py-2 text-sm"
            value={sendOn}
            onChange={(event) => setSendOn(event.target.value)}
          />
          {isLastMain ? (
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={msme}
                disabled={!canToggleMsme}
                onChange={(event) => setMsme(event.target.checked)}
              />
              Include MSME note on this final reminder
              {!canToggleMsme ? (
                <span className="text-xs text-slate-400">(add Udyam number in Settings first)</span>
              ) : null}
            </label>
          ) : null}
        </div>
      ) : (
        <div className="mt-4">
          <p className="text-sm font-medium">{message.subject}</p>
          <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{message.body}</p>
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        {editable ? (
          <ActionButton
            disabled={disabled}
            onClick={async () => {
              const updated = await patchMessage(message.id, {
                subject,
                body,
                send_on: sendOn || undefined,
                include_msme_note: isLastMain ? msme : undefined,
              });
              await onSaved(updated);
            }}
          >
            Save edits
          </ActionButton>
        ) : null}
        <ActionButton secondary disabled={disabled} onClick={() => void onPreview()}>
          Preview email
        </ActionButton>
        {planStatus === "active" && ["scheduled", "held"].includes(message.status) ? (
          <ActionButton disabled={disabled} onClick={() => void onSendNow()}>
            Send now
          </ActionButton>
        ) : null}
        {editable ? (
          <ActionButton secondary disabled={disabled} onClick={() => void onDelete()}>
            Delete
          </ActionButton>
        ) : null}
      </div>
    </article>
  );
}
