import type { Metadata } from "next";
import "./globals.css";

import { I18nProvider } from "@/lib/i18n/provider";
import { getMessages } from "@/lib/i18n/messages";
import { defaultLocale } from "@/lib/i18n/config";

export const metadata: Metadata = {
  title: "Prompt Optimization Studio",
  description: "Local workflow console for prompt evaluation and optimization",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang={defaultLocale} suppressHydrationWarning>
      <body>
        <I18nProvider locale={defaultLocale} messages={getMessages(defaultLocale)}>
          {children}
        </I18nProvider>
      </body>
    </html>
  );
}
