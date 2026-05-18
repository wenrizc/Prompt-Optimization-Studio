import { notFound } from "next/navigation";
import { PropsWithChildren } from "react";

import { isLocale, Locale } from "@/lib/i18n/config";
import { I18nProvider } from "@/lib/i18n/provider";
import { getMessages } from "@/lib/i18n/messages";

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

  const locale = lang as Locale;
  return (
    <I18nProvider locale={locale} messages={getMessages(locale)}>
      {children}
    </I18nProvider>
  );
}
