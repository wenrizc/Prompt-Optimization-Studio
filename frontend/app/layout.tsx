import type { Metadata } from "next";
import "./globals.css";

import { I18nProvider } from "@/lib/i18n/provider";
import { getMessages } from "@/lib/i18n/messages";

export const metadata: Metadata = {
  title: "Prompt Optimization Studio",
  description: "Local workflow console for prompt evaluation and optimization",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <I18nProvider locale="en" messages={getMessages("en")}>
          {children}
        </I18nProvider>
      </body>
    </html>
  );
}
