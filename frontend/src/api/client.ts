export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  workspace_id: string;
}

export interface WorkspaceUser {
  id: string;
  email: string;
  name: string;
  role: string;
}

export interface RoleInfo {
  id: string;
  label: string;
  description: string;
}

export interface DashboardTotals {
  outstanding_display: string;
  outstanding_count: number;
  overdue_display: string;
  overdue_count: number;
  due_soon_display: string;
  due_soon_count: number;
  promised_display: string;
  promised_count: number;
  open_issues_count: number;
  payment_reported_count: number;
  awaiting_approval_count: number;
  held_reminders_count: number;
  needs_attention_count: number;
  collected_30d_display: string;
}

export interface AttentionItem {
  type: string;
  invoice_id: string;
  invoice_number: string;
  client_name: string;
  summary: string;
  owner_options: string[];
  occurred_at: string | null;
}

export interface InvoiceSummary {
  id: string;
  client_name: string;
  invoice_number: string;
  amount_display: string;
  outstanding_display: string;
  due_date: string;
  days_overdue: number;
  status: string;
  plan_status: string;
  next_reminder: string | null;
}

export interface InvoiceMessage {
  id: string;
  kind: string;
  step: number;
  tone: string;
  subject: string;
  body: string;
  status: string;
  include_msme_note: boolean;
  send_on: string | null;
  send_at: string | null;
  sent_to: string | null;
  error: string | null;
}

export interface InvoiceEvent {
  id: string;
  actor: string;
  type: string;
  data: Record<string, unknown> | null;
  created_at: string | null;
}

export interface OutboxItem {
  id: string;
  kind: string;
  subject: string;
  to: string[];
  html: string;
  text: string;
  created_at: string | null;
}

export interface InvoiceDetail extends InvoiceSummary {
  description: string | null;
  issue_date: string;
  client_page_url: string;
  client: {
    id: string;
    name: string;
    contact_name: string;
    email: string;
    cc_emails: string[];
    relationship_notes: string | null;
  };
  promise_date: string | null;
  promise_count: number;
  promise_broken: boolean;
  reported_amount_display: string | null;
  reported_reference: string | null;
  reported_paid_on: string | null;
  reported_at: string | null;
  issue_kind: string | null;
  issue_reason: string | null;
  issue_note: string | null;
  messages: InvoiceMessage[];
  events: InvoiceEvent[];
  outbox: OutboxItem[];
  workspace_has_udyam: boolean;
}

export interface WorkspaceSettings {
  business_name: string;
  sender_name: string;
  reply_to_email: string | null;
  bank_account_name: string | null;
  bank_account_number: string | null;
  ifsc: string | null;
  upi_id: string | null;
  udyam_number: string | null;
  send_hour_ist: number;
  send_minute_ist: number;
  logo_data_url: string | null;
  favicon_data_url: string | null;
  accent_color: string;
  retention_days_paid: number;
  retention_keep_audit: boolean;
  is_demo: boolean;
  claude_connection_url: string;
  msme_note_preview: string | null;
}

export function login(email: string, password: string): Promise<User> {
  return request<User>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function logout(): Promise<{ status: string }> {
  return request("/api/auth/logout", { method: "POST" });
}

export function fetchMe(): Promise<User> {
  return request<User>("/api/auth/me");
}

export function fetchDashboard(): Promise<{
  totals: DashboardTotals;
  attention: AttentionItem[];
  invoices: InvoiceSummary[];
}> {
  return request("/api/dashboard");
}

export function fetchInvoice(id: string): Promise<InvoiceDetail> {
  return request(`/api/invoices/${id}`);
}

export function postInvoiceAction(
  id: string,
  action:
    | "approve"
    | "pause"
    | "resume"
    | "cancel"
    | "confirm-payment"
    | "reject-payment"
    | "resolve-issue",
): Promise<InvoiceDetail> {
  return request(`/api/invoices/${id}/${action}`, { method: "POST" });
}

export function patchMessage(
  messageId: string,
  payload: {
    subject?: string;
    body?: string;
    send_on?: string;
    include_msme_note?: boolean;
  },
): Promise<InvoiceDetail> {
  return request(`/api/messages/${messageId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteMessage(messageId: string): Promise<InvoiceDetail> {
  return request(`/api/messages/${messageId}`, { method: "DELETE" });
}

export function previewMessage(messageId: string): Promise<{
  subject: string;
  html: string;
  text: string;
  to: string[];
  from_display: string;
}> {
  return request(`/api/messages/${messageId}/preview`);
}

export function sendMessageNow(messageId: string): Promise<{
  status: string;
  outbound_email_id?: string;
  client_page_url?: string;
}> {
  return request(`/api/messages/${messageId}/send-now`, { method: "POST" });
}

export function fetchSettings(): Promise<WorkspaceSettings> {
  return request("/api/settings");
}

export function saveSettings(payload: Partial<WorkspaceSettings>): Promise<WorkspaceSettings> {
  return request("/api/settings", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function regenerateClaudeLink(): Promise<WorkspaceSettings> {
  return request("/api/settings/regenerate-claude-link", { method: "POST" });
}

export function resetSampleData(): Promise<{ status: string; summary: string }> {
  return request("/api/demo/reset", { method: "POST" });
}

export function fetchUsers(): Promise<{ users: WorkspaceUser[]; roles: RoleInfo[] }> {
  return request("/api/users");
}

export function createUser(payload: {
  name: string;
  email: string;
  password: string;
  role: string;
}): Promise<WorkspaceUser> {
  return request("/api/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateUserRole(userId: string, role: string): Promise<WorkspaceUser> {
  return request(`/api/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
}

export function removeUser(userId: string): Promise<{ status: string }> {
  return request(`/api/users/${userId}`, { method: "DELETE" });
}
