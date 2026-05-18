import { notFound } from "next/navigation";
import { PropsWithChildren } from "react";

import { isLocale, Locale } from "@/lib/i18n/config";
import { getMessages } from "@/lib/i18n/messages";
import { I18nProvider } from "@/lib/i18n/provider";

export function generateStaticParams() {
  return [{ lang: "en" }, { lang: "zh" }];
}

export default async function LocaleLayout({
  children,
  params,
}: PropsWithChildren<{ params: Promise<{ lang: string }> }>) {
  const { lang } = await params;
  if (!isLocale(lang)) {
    notFound();
  }

  return <I18nProvider locale={lang as Locale} messages={getMessages(lang as Locale)}>{children}</I18nProvider>;
}
