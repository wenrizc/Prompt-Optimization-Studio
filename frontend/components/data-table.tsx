import { useI18n } from "@/lib/i18n/provider";

type Row = Record<string, unknown>;

export function DataTable({ rows }: { rows: Row[] }) {
  const { t } = useI18n();
  if (rows.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-stone-400/40 p-6 text-sm text-stone-500">
        {t("common.noData")}
      </div>
    );
  }

  const columns = Object.keys(rows[0]);
  return (
    <div className="overflow-x-auto rounded-2xl border border-stone-900/10">
      <table className="min-w-full divide-y divide-stone-900/10 text-sm">
        <thead className="bg-stone-100/70">
          <tr>
            {columns.map((column) => (
              <th key={column} className="px-4 py-3 text-left font-medium text-stone-700">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-900/10 bg-white">
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column} className="px-4 py-3 align-top text-stone-700">
                  <pre className="whitespace-pre-wrap break-words font-mono text-xs">
                    {typeof row[column] === "string"
                      ? (row[column] as string)
                      : JSON.stringify(row[column], null, 2)}
                  </pre>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
