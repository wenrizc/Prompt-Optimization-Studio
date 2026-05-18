"use client";

import Link from "next/link";
import { PropsWithChildren } from "react";

import { Locale, locales, useI18n } from "@/lib/i18n/provider";

const navItems = [
  { href: "/", key: "nav.home" },
  { href: "/projects", key: "nav.projects" },
  { href: "/datasets/generator", key: "nav.datasetGenerator" },
  { href: "/datasets/import", key: "nav.datasetImport" },
  { href: "/datasets/editor", key: "nav.datasetEditor" },
  { href: "/prompts", key: "nav.prompts" },
  { href: "/evaluations", key: "nav.evaluations" },
  { href: "/optimization-runs", key: "nav.optimizationRuns" },
  { href: "/reports", key: "nav.reports" },
  { href: "/run-comparison", key: "nav.runComparison" },
];

export function AppShell({ children }: PropsWithChildren) {
  const { locale, t, href, switchLocalePath } = useI18n();

  return (
    <div className="min-h-screen">
      <header className="border-b border-stone-900/10 bg-[rgba(255,253,248,0.8)] backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-6 py-5">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-stone-500">
              {t("app.name")}
            </p>
            <h1 className="text-2xl font-semibold text-stone-900">
              {t("app.shellTitle")}
            </h1>
          </div>
          <div className="flex max-w-3xl flex-col items-end gap-3">
            <div className="flex items-center gap-2 rounded-full border border-stone-900/10 bg-white px-3 py-2 text-xs text-stone-600">
              <span>{t("app.language")}</span>
              {locales.map((item) => (
                <Link
                  key={item}
                  href={switchLocalePath(item as Locale)}
                  className={`rounded-full px-3 py-1 font-medium ${
                    locale === item ? "bg-stone-900 text-white" : "text-stone-700"
                  }`}
                >
                  {item === "en" ? t("app.english") : t("app.chinese")}
                </Link>
              ))}
            </div>
            <nav className="flex flex-wrap justify-end gap-2">
            {navItems.map((item) => (
              <Link
                key={item.href}
                className="rounded-full border border-stone-900/10 bg-white px-4 py-2 text-sm text-stone-700 transition hover:border-teal-700 hover:text-teal-700"
                href={href(item.href)}
              >
                {t(item.key)}
              </Link>
            ))}
            </nav>
          </div>
        </div>
      </header>
      <main className="mx-auto flex max-w-7xl flex-col gap-6 px-6 py-8">{children}</main>
    </div>
  );
}
