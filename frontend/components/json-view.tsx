import { useI18n } from "@/lib/i18n/provider";

export function JsonView({
  value,
  emptyLabel,
}: {
  value: unknown;
  emptyLabel?: string;
}) {
  const { t } = useI18n();
  const resolvedEmptyLabel = emptyLabel ?? t("common.noData");

  if (value == null || value === "") {
    return (
      <div className="rounded-2xl border border-dashed border-stone-300 bg-white/70 p-4 text-sm text-stone-500">
        {resolvedEmptyLabel}
      </div>
    );
  }

  return (
    <pre className="overflow-x-auto rounded-3xl bg-stone-950 p-4 text-xs leading-6 text-stone-100">
      {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
    </pre>
  );
}
