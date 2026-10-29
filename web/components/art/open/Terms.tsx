// Plate 2: how long each set is under which licence, and what the source-available licence lets you do. The timeline
// uses the same line language as the map: dashed while it is source-available, solid when it is open. Still. It has a
// wide and a narrow version (same layout, different geometry) so the type keeps its size and the rows keep their air.
import type { Dict } from "@/lib/i18n";
import { site } from "@/lib/site";
import { ArtFrame } from "../ArtFrame";

type T = Dict["open"]["art"]["terms"];

type Geo = {
  w: number;
  xEnd: number; // two years after publication
  row1: number;
  row2: number;
  h: number;
  cls: string;
};
const TOP = 26; // the two vertical lines run from here to the bottom
const WIDE: Geo = { w: 640, xEnd: 420, row1: 70, row2: 160, h: 200, cls: "only-wide" };
const NARROW: Geo = { w: 360, xEnd: 236, row1: 74, row2: 168, h: 212, cls: "only-narrow" };

/** An arrowhead at the right end of a line: time goes on. */
const head = (w: number, y: number) => `M${w - 7} ${y - 5} L${w} ${y} L${w - 7} ${y + 5}`;

function Timeline({ t, g }: { t: T; g: Geo }) {
  const { w, xEnd, row1, row2, h } = g;
  return (
    <ArtFrame w={w} h={h} label={t.label} className={`art-terms ${g.cls}`}>
      {/* the two moments: publication and two years later */}
      <line className="ln w075 dim" x1={0} y1={TOP} x2={0} y2={h - 6} />
      <line className="ln w075 dim" x1={xEnd} y1={TOP} x2={xEnd} y2={h - 6} />
      <text className="axis" x={0} y={12}>{t.start}</text>
      <text className="axis" x={xEnd} y={12} textAnchor="middle">{t.end}</text>

      {/* source-available: dashed for two years, then Apache 2.0 */}
      <text className="row" x={12} y={row1 - 18}>{t.srcRow}</text>
      <path className="ln w15 dash" d={`M0 ${row1} H${xEnd}`} />
      <path className="ln w15" d={`M${xEnd} ${row1} H${w} ${head(w, row1)}`} />
      <text className="halo" x={xEnd / 2} y={row1 + 24} textAnchor="middle">{t.srcPhase}</text>
      <text className="halo" x={(xEnd + w) / 2} y={row1 + 24} textAnchor="middle">{t.srcAfter}</text>

      {/* open source: solid from the start */}
      <text className="row" x={12} y={row2 - 18}>{t.openRow}</text>
      <path className="ln w15" d={`M0 ${row2} H${w} ${head(w, row2)}`} />
      <text className="halo" x={xEnd / 2} y={row2 + 24} textAnchor="middle">{t.openPhase}</text>
    </ArtFrame>
  );
}

export function TermsArt({ t }: { t: T }) {
  return (
    <figure className="figure terms">
      <Timeline t={t} g={WIDE} />
      <Timeline t={t} g={NARROW} />

      <div className="terms-cols">
        {[t.can, t.cannot].map((col) => (
          <div key={col.title}>
            <h3>{col.title}</h3>
            <ul>
              {col.items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <figcaption>
        <span>{t.before}</span>
        <a href={`${site.repo}/blob/main/LICENSE-FSL`} target="_blank" rel="noopener noreferrer">{t.full}</a>
      </figcaption>
    </figure>
  );
}
