// Public settings. Anything that identifies a person or a sending domain comes from the environment, so the site
// can be built before they are decided (the design notes, section 10).
export const site = {
  url: process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000",
  repo: "https://github.com/raaulalonso/caseback",
  controller: process.env.NEXT_PUBLIC_CONTROLLER_NAME || "",
  contact: process.env.NEXT_PUBLIC_CONTACT_EMAIL || "",
};

export function formatDate(iso: string, lang: string) {
  return new Intl.DateTimeFormat(lang === "es" ? "es-ES" : "en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(`${iso}T12:00:00Z`));
}
