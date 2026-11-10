const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  promised: "Payment promised",
  payment_reported: "Payment reported",
  issue_raised: "Waiting on you",
  paid: "Paid",
  cancelled: "Cancelled",
};

const PLAN_LABELS: Record<string, string> = {
  draft: "Awaiting approval",
  active: "Follow-ups scheduled",
  paused: "Paused",
  completed: "Sequence finished",
  cancelled: "Cancelled",
};

const MESSAGE_STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  scheduled: "Scheduled",
  held: "On hold",
  sending: "Sending",
  sent: "Sent",
  failed: "Failed",
  cancelled: "Removed",
};

const ATTENTION_TITLES: Record<string, string> = {
  issue_raised: "Client needs something",
  payment_reported: "Verify payment",
  promise_broken: "Promise missed",
  plan_awaiting_approval: "Plan ready to approve",
  sequence_ended_unpaid: "Reminders finished, still unpaid",
  send_failed: "Reminder could not be delivered",
};

const EVENT_LABELS: Record<string, string> = {
  created_by_claude: "Follow-up plan drafted in Claude",
  plan_approved: "You approved the follow-up plan",
  plan_paused: "Follow-ups paused",
  plan_resumed: "Follow-ups resumed",
  payment_reported: "Client reported a payment",
  payment_promised: "Client promised a payment date",
  issue_raised: "Client raised a need or problem",
  promise_broken: "Promised date was missed",
  payment_confirmed: "You confirmed payment received",
  payment_report_rejected: "You marked payment as not received",
  issue_resolved_resumed: "Issue resolved and follow-ups resumed",
  messages_replaced: "Follow-up messages were rewritten",
  edited_by_claude: "Message edited in Claude",
  edited_by_owner: "You edited a message",
  invoice_cancelled: "Invoice cancelled",
  message_sent: "Reminder sent",
  message_send_failed: "Reminder failed to send",
  sequence_completed_unpaid: "All reminders sent; invoice still open",
  client_viewed: "Client opened the payment page",
  seeded_open_active: "Sample invoice prepared",
};

export function invoiceStatusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

export function planStatusLabel(status: string): string {
  return PLAN_LABELS[status] ?? status;
}

export function messageStatusLabel(status: string): string {
  return MESSAGE_STATUS_LABELS[status] ?? status;
}

export function attentionTitle(type: string): string {
  return ATTENTION_TITLES[type] ?? "Needs your attention";
}

export function eventLabel(type: string): string {
  return EVENT_LABELS[type] ?? type.replaceAll("_", " ");
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function relativeTime(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const diffMs = Date.now() - date.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 60) return `${Math.max(mins, 1)}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 48) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
