import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, Instrument_Sans } from "next/font/google";
import { notFound } from "next/navigation";
import { dict, isLocale, locales } from "@/lib/i18n";
import { site } from "@/lib/site";
import "../globals.css";

const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["300", "400", "500"], variable: "--font-mono", display: "swap" });
const sans = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-sans", display: "swap" });

// Display face: the wordmark and the headline. Plex Sans stays for body text and Plex Mono for numbers and the engraving.
const mark = Instrument_Sans({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-mark", display: "swap" });

export const dynamicParams = false;

export function generateStaticParams() {
  return locales.map((lang) => ({ lang }));
}

export async function generateMetadata({ params }: LayoutProps<"/[lang]">): Promise<Metadata> {
  const { lang } = await params;
  const t = dict(lang);
  return {
    metadataBase: new URL(site.url),
    title: { default: t.meta.title, template: `%s · ${t.meta.title}` },
    description: t.meta.description,
    alternates: { languages: { en: "/en", es: "/es" } },
    openGraph: { title: t.meta.title, description: t.meta.description, siteName: "Caseback", type: "website", locale: lang },
  };
}

export const viewport: Viewport = { themeColor: "#000000", width: "device-width", initialScale: 1, colorScheme: "dark" };

export default async function RootLayout({ children, params }: LayoutProps<"/[lang]">) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  return (
    <html lang={lang} className={`${mono.variable} ${sans.variable} ${mark.variable}`}>
      <body>{children}</body>
    </html>
  );
}
