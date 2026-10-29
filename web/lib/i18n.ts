import { en } from "@/content/en";
import { es } from "@/content/es";

export const locales = ["en", "es"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "en";

export type Dict = typeof en;

const dicts: Record<Locale, Dict> = { en, es };

export function isLocale(v: string): v is Locale {
  return (locales as readonly string[]).includes(v);
}

export function dict(lang: string): Dict {
  return dicts[isLocale(lang) ? lang : defaultLocale];
}

export const sections = ["wear", "measure", "app", "open"] as const;
export type Section = (typeof sections)[number];

/** Same path in the other language. */
export function swapLocale(path: string, to: Locale) {
  const parts = path.split("/");
  if (isLocale(parts[1] ?? "")) parts[1] = to;
  else parts.splice(1, 0, to);
  return parts.join("/") || `/${to}`;
}
