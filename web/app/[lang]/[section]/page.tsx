import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { TopBar } from "@/components/chrome/TopBar";
import { plateArt } from "@/components/art";
import { PlateDeck } from "@/components/section/PlateDeck";
import { dict, isLocale, locales, sections, type Locale, type Section } from "@/lib/i18n";

export const dynamicParams = false;

export function generateStaticParams() {
  return locales.flatMap((lang) => sections.map((section) => ({ lang, section })));
}

export async function generateMetadata({ params }: PageProps<"/[lang]/[section]">): Promise<Metadata> {
  const { lang, section } = await params;
  const t = dict(lang);
  if (!(sections as readonly string[]).includes(section)) return {};
  return { title: t[section as Section].title };
}

export default async function SectionPage({ params }: PageProps<"/[lang]/[section]">) {
  const { lang, section } = await params;
  if (!isLocale(lang) || !(sections as readonly string[]).includes(section)) notFound();
  const t = dict(lang);
  const key = section as Section;
  const s = t[key];
  const plates = s.plates as { title: string; body: string[] }[];
  const next = sections[(sections.indexOf(key) + 1) % sections.length];

  return (
    <main className={`section section-${key}`}>
      <TopBar lang={lang as Locale} t={t} back section={s.title} />
      <h1 className="sr-only">{s.title}</h1>
      <PlateDeck count={plates.length} label={t.nav.plate} of={t.nav.of}>
        {plates.map((p, i) => (
          <section key={i} className="plate" aria-labelledby={`p${i}`}>
            <div className="plate-text">
              <h2 id={`p${i}`}>{p.title}</h2>
              {p.body.map((b, j) => (
                <p key={j} className="body">{b}</p>
              ))}
            </div>
            <div className="plate-art">
              {plateArt(key, i, t, lang as Locale)}
            </div>
          </section>
        ))}
        <footer className="next">
          <Link href={`/${lang}`} className="next-home">← {t.nav.back}</Link>
          <Link href={`/${lang}/${next}`} className="next-section">
            <span className="next-label">{t[next].title}</span>
            <span aria-hidden> →</span>
          </Link>
        </footer>
      </PlateDeck>
    </main>
  );
}
