import { PropsWithChildren } from "react";

export function Panel({
  title,
  description,
  children,
}: PropsWithChildren<{ title: string; description?: string }>) {
  return (
    <section className="rounded-[28px] border border-stone-900/10 bg-[var(--surface)] p-6 shadow-panel">
      <div className="mb-4">
        <h2 className="text-xl font-semibold text-stone-900">{title}</h2>
        {description ? <p className="mt-1 text-sm text-stone-600">{description}</p> : null}
      </div>
      {children}
    </section>
  );
}
