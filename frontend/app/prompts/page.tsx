"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { defaultLocale, isLocale, Locale } from "@/lib/i18n/config";

function detectLocale(): Locale {
  if (typeof navigator === "undefined") return defaultLocale;
  const lang = navigator.language.split("-")[0];
  return isLocale(lang) ? lang : defaultLocale;
}

export default function RedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace(`/${detectLocale()}/prompts`);
  }, [router]);
  return null;
}
