type Translate = (key: string, values?: Record<string, string | number>) => string;

function translateEnumValue(t: Translate, key: string, fallback: string) {
  const translated = t(key);
  return translated === key ? fallback : translated;
}

export function formatSplitLabel(t: Translate, value: string | null | undefined) {
  const label = value || "unassigned";
  return translateEnumValue(t, `common.split.${label}`, label);
}

export function formatDatasetSourceLabel(t: Translate, value: string | null | undefined) {
  const label = value || "manual";
  return translateEnumValue(t, `common.datasetSource.${label}`, label);
}
