import Link from "next/link";
import type { Dict, Locale } from "@/lib/i18n";
import { site } from "@/lib/site";
import { Brand } from "./Brand";
import { LangSwitch } from "./LangSwitch";

/** Wordmark on the left; repository and language on the right. */
export function TopBar({ lang, t, back, home, section }: { lang: Locale; t: Dict; back?: boolean; home?: boolean; section?: string }) {
  return (
    <header className={home ? "top top-home" : "top"}>
      {!home && (
        <Link href={`/${lang}`} className="wordmark" aria-label={back ? t.nav.back : t.nav.home}>
          {back && <span className="back-arrow" aria-hidden>←</span>}
          <Brand />
        </Link>
      )}
      {section && <span className="crumb">{section}</span>}
      <nav className="topnav" aria-label="Caseback">
        <a href={site.repo} target="_blank" rel="noopener noreferrer">
          {t.nav.github}<span aria-hidden> ↗</span>
        </a>
        <LangSwitch lang={lang} label={t.nav.language} />
      </nav>
    </header>
  );
}
