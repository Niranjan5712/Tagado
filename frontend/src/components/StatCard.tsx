export function StatCard({
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
        emphasize ? "border-rose-200 bg-rose-50/70" : "border-[var(--line)] bg-[var(--card)]"
      }`}
    >
      <h3 className="text-sm font-semibold text-[var(--ink)]">{title}</h3>
      <p className="mt-1 text-xs leading-relaxed text-slate-500">{description}</p>
      <p className="mt-3 text-2xl font-semibold tracking-tight">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{meta}</p>
    </article>
  );
}
