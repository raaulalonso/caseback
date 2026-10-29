"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { locales, swapLocale, type Locale } from "@/lib/i18n";

/** EN · ES, keeping the current page. */
export function LangSwitch({ lang, label }: { lang: Locale; label: string }) {
  const path = usePathname() || `/${lang}`;
  return (
    <span className="lang" role="group" aria-label={label}>
      {locales.map((l) =>
        l === lang ? (
          <span key={l} className="lang-on" aria-current="true">{l.toUpperCase()}</span>
        ) : (
          <Link key={l} href={swapLocale(path, l)} hrefLang={l} lang={l}>{l.toUpperCase()}</Link>
        ),
      )}
    </span>
  );
}
