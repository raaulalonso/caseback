// Plate 3: the commands that reproduce the figures. They are the ones in the READMEs and in .github/workflows/ci.yml.
import type { Dict } from "@/lib/i18n";
import { site } from "@/lib/site";

type T = Dict["open"]["art"]["verify"];

export function VerifyArt({ t }: { t: T }) {
  return (
    <figure className="figure verify" role="group" aria-label={t.label}>
      <ol className="verify-rows">
        {t.rows.map((r) => (
          <li key={r.name} className="verify-row">
            <div className="verify-name">
              <strong>{r.name}</strong>
              <span>{r.detail}</span>
            </div>
            <code className="verify-cmd">{r.cmd}</code>
          </li>
        ))}
      </ol>
      <figcaption>
        <span>{t.note}</span>
        <span className="verify-links">
          <a href={site.repo} target="_blank" rel="noopener noreferrer">{t.repo}</a>
          <a href={`${site.repo}/blob/main/CONTRIBUTING.md`} target="_blank" rel="noopener noreferrer">{t.contribute}</a>
        </span>
      </figcaption>
    </figure>
  );
}
