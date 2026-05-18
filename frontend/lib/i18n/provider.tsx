"use client";

import { createContext, PropsWithChildren, useContext, useEffect, useMemo } from "react";
import { usePathname } from "next/navigation";

import { defaultLocale, isLocale, Locale, locales } from "@/lib/i18n/config";
import { Dictionary, getMessages } from "@/lib/i18n/messages";

type I18nContextValue = {
  locale: Locale;
  messages: Dictionary;
  t: (key: string, values?: Record<string, string | number>) => string;
  tm: <T = unknown>(key: string) => T;
  href: (path: string) => string;
  switchLocalePath: (nextLocale: Locale) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({
  locale,
  messages,
  children,
}: PropsWithChildren<{ locale: Locale; messages?: Dictionary }>) {
  const pathname = usePathname();
  const resolvedMessages = messages ?? getMessages(locale);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const value = useMemo<I18nContextValue>(() => {
    const translate = (key: string, values?: Record<string, string | number>) => {
      const resolved = resolvePath(resolvedMessages, key);
      if (typeof resolved !== "string") {
        return key;
      }
      return interpolate(resolved, values);
    };

    const translateMessage = <T,>(key: string): T => resolvePath(resolvedMessages, key) as T;

    return {
      locale,
      messages: resolvedMessages,
      t: translate,
      tm: translateMessage,
      href: (path: string) => localizePath(path, locale),
      switchLocalePath: (nextLocale: Locale) => switchLocale(pathname || "/", nextLocale),
    };
  }, [locale, pathname, resolvedMessages]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used within an I18nProvider");
  }
  return context;
}

function resolvePath(source: unknown, key: string): unknown {
  return key.split(".").reduce<unknown>((current, part) => {
    if (current && typeof current === "object" && part in (current as Record<string, unknown>)) {
      return (current as Record<string, unknown>)[part];
    }
    return undefined;
  }, source);
}

function interpolate(template: string, values?: Record<string, string | number>) {
  if (!values) {
    return template;
  }
  return template.replace(/\{(\w+)\}/g, (_match, key) => String(values[key] ?? `{${key}}`));
}

export function localizePath(path: string, locale: Locale): string {
  if (!path.startsWith("/")) {
    return path;
  }
  if (path === "/") {
    return `/${locale}`;
  }
  const segments = path.split("/");
  const maybeLocale = segments[1];
  if (maybeLocale && isLocale(maybeLocale)) {
    segments[1] = locale;
    return segments.join("/");
  }
  return `/${locale}${path}`;
}

export function switchLocale(pathname: string, nextLocale: Locale): string {
  const segments = pathname.split("/");
  const maybeLocale = segments[1];
  if (maybeLocale && isLocale(maybeLocale)) {
    segments[1] = nextLocale;
    return segments.join("/") || `/${nextLocale}`;
  }
  return localizePath(pathname, nextLocale);
}

export { defaultLocale, locales };
export type { Locale };
