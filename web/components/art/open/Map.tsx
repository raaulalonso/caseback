// Plate 1: the repository as a map of its folders, in the two sets the licences make. A dashed spine is source-available
// (readable, not for a competing product), a solid spine is open source. The folders and licences are those of NOTICE.
import type { Dict } from "@/lib/i18n";
import { site } from "@/lib/site";

type T = Dict["open"]["art"]["map"];

export function MapArt({ t }: { t: T }) {
  return (
    <figure className="figure map" role="group" aria-label={t.label}>
      {t.groups.map((g, i) => (
        <section key={g.name} className={`map-group ${i === 0 ? "src" : "free"}`}>
          <header className="map-head">
            <h3>{g.name}</h3>
            <p>{g.terms}</p>
          </header>
          <ol className="map-rows">
            {g.rows.map((r) => (
              <li key={r.name} className="map-row">
                <div className="map-name">
                  <strong>{r.name}</strong>
                  <span>{r.detail}</span>
                </div>
                <div className="map-paths mono">
                  {r.paths.map((p) => (
                    <a key={p} href={`${site.repo}/tree/main/${p}`} target="_blank" rel="noopener noreferrer">{p}</a>
                  ))}
                </div>
                <div className="map-lic">{r.licence}</div>
              </li>
            ))}
          </ol>
        </section>
      ))}
      <figcaption>{t.note}</figcaption>
    </figure>
  );
}
