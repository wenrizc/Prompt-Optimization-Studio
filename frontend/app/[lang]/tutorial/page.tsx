"use client";

import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { Panel } from "@/components/panel";
import { useI18n } from "@/lib/i18n/provider";

export default function TutorialPage() {
  const { t, tm, href } = useI18n();
  const steps = tm<Array<{ title: string; description: string; href: string; cta: string }>>("tutorial.steps") ?? [];
  const tips = tm<Array<string>>("tutorial.tips") ?? [];

  return (
    <AppShell>
      <Panel title={t("tutorial.title")} description={t("tutorial.description")}>
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-[24px] border border-stone-900/10 bg-white p-5">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-500">{t("tutorial.prereqTitle")}</p>
            <p className="mt-2 text-sm leading-7 text-stone-700 whitespace-pre-wrap">{t("tutorial.prereqBody")}</p>
          </div>
          <div className="rounded-[24px] border border-stone-900/10 bg-white p-5">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-500">{t("tutorial.goalTitle")}</p>
            <p className="mt-2 text-sm leading-7 text-stone-700">{t("tutorial.goalBody")}</p>
          </div>
          <div className="rounded-[24px] border border-stone-900/10 bg-white p-5">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-500">{t("tutorial.resultTitle")}</p>
            <p className="mt-2 text-sm leading-7 text-stone-700">{t("tutorial.resultBody")}</p>
          </div>
        </div>
      </Panel>

      <Panel title={t("tutorial.stepsTitle")} description={t("tutorial.stepsDescription")}>
        <div className="grid gap-4">
          {steps.map((step, index) => (
            <div key={step.title} className="rounded-[28px] border border-stone-900/10 bg-white p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="max-w-3xl">
                  <p className="text-xs uppercase tracking-[0.18em] text-stone-500">
                    {t("tutorial.stepLabel", { step: index + 1 })}
                  </p>
                  <h3 className="mt-2 text-lg font-semibold text-stone-900">{step.title}</h3>
                  <p className="mt-3 text-sm leading-7 text-stone-600">{step.description}</p>
                </div>
                <Link
                  href={href(step.href)}
                  className="inline-flex rounded-full bg-stone-900 px-4 py-2 text-sm font-medium text-white"
                >
                  {step.cta}
                </Link>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title={t("tutorial.tipsTitle")} description={t("tutorial.tipsDescription")}>
        <div className="grid gap-3">
          {tips.map((tip) => (
            <div key={tip} className="rounded-[24px] border border-stone-900/10 bg-white p-4 text-sm leading-7 text-stone-700">
              {tip}
            </div>
          ))}
        </div>
      </Panel>
    </AppShell>
  );
}
