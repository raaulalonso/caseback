import { NextResponse, type NextRequest } from "next/server";

// Sends a request without a language prefix to /en or /es, from the browser's Accept-Language.
const LOCALES = ["en", "es"];

function pick(header: string | null) {
  const langs = (header ?? "")
    .split(",")
    .map((part) => {
      const [tag, q] = part.trim().split(";q=");
      return { tag: tag.toLowerCase().split("-")[0], q: q ? Number(q) : 1 };
    })
    .sort((a, b) => b.q - a.q);
  return langs.find((l) => LOCALES.includes(l.tag))?.tag ?? "en";
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (LOCALES.some((l) => pathname === `/${l}` || pathname.startsWith(`/${l}/`))) return;
  const url = request.nextUrl.clone();
  url.pathname = `/${pick(request.headers.get("accept-language"))}${pathname === "/" ? "" : pathname}`;
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!_next|api|icon|favicon|robots.txt|sitemap.xml|.*\\..*).*)"],
};
