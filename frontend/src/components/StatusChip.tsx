import { invoiceStatusLabel, messageStatusLabel, planStatusLabel } from "@/lib/labels";

const TONE: Record<string, string> = {
  open: "bg-sky-50 text-sky-800 border-sky-200",
  promised: "bg-amber-50 text-amber-900 border-amber-200",
  payment_reported: "bg-violet-50 text-violet-900 border-violet-200",
  issue_raised: "bg-rose-50 text-rose-900 border-rose-200",
  paid: "bg-emerald-50 text-emerald-900 border-emerald-200",
  cancelled: "bg-slate-100 text-slate-600 border-slate-200",
  draft: "bg-orange-50 text-orange-900 border-orange-200",
  active: "bg-teal-50 text-teal-900 border-teal-200",
  paused: "bg-yellow-50 text-yellow-900 border-yellow-200",
  completed: "bg-slate-100 text-slate-700 border-slate-200",
  scheduled: "bg-teal-50 text-teal-900 border-teal-200",
  held: "bg-amber-50 text-amber-900 border-amber-200",
  sent: "bg-emerald-50 text-emerald-900 border-emerald-200",
  failed: "bg-rose-50 text-rose-900 border-rose-200",
  sending: "bg-sky-50 text-sky-800 border-sky-200",
};

interface StatusChipProps {
  value: string;
  kind?: "invoice" | "plan" | "message";
}

export function StatusChip({ value, kind = "invoice" }: StatusChipProps) {
  const label =
    kind === "plan"
      ? planStatusLabel(value)
      : kind === "message"
        ? messageStatusLabel(value)
        : invoiceStatusLabel(value);

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${
        TONE[value] ?? "bg-slate-100 text-slate-700 border-slate-200"
      }`}
    >
      {label}
    </span>
  );
}
