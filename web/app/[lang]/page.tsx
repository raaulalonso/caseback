import { TopBar } from "@/components/chrome/TopBar";
import { Brand } from "@/components/chrome/Brand";
import { HomeStage } from "@/components/home/HomeStage";
import { dict, type Locale } from "@/lib/i18n";

export default async function Home({ params }: PageProps<"/[lang]">) {
  const { lang } = (await params) as { lang: Locale };
  const t = dict(lang);
  return (
    <main className="stage">
      <TopBar lang={lang} t={t} home />
      <div className="intro-copy">
        <h1 className="headline">{t.home.lead}</h1>
        <p className="sub">{t.home.sub}</p>
      </div>
      <HomeStage lang={lang} t={t} />
      <footer className="foot">
        <p className="status">{t.home.status}</p>
        <p className="signature"><Brand /></p>
      </footer>
    </main>
  );
}
