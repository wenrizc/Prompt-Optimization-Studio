import { useI18n } from "@/lib/i18n/provider";

const statusStyles: Record<string, string> = {
  succeeded: "bg-emerald-100 text-emerald-800 border-emerald-200",
  success: "bg-emerald-100 text-emerald-800 border-emerald-200",
  running: "bg-sky-100 text-sky-800 border-sky-200",
  queued: "bg-amber-100 text-amber-800 border-amber-200",
  failed: "bg-rose-100 text-rose-800 border-rose-200",
  cancelled: "bg-stone-200 text-stone-700 border-stone-300",
  cancel_requested: "bg-orange-100 text-orange-800 border-orange-200",
  active: "bg-emerald-100 text-emerald-800 border-emerald-200",
  archived: "bg-stone-200 text-stone-700 border-stone-300",
};

export function StatusChip({ value }: { value: string | null | undefined }) {
  const { t } = useI18n();
  const label = value || "unknown";
  const className = statusStyles[label] ?? "bg-stone-100 text-stone-700 border-stone-200";
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${className}`}>
      {t(`common.status.${label}`)}
    </span>
  );
}
