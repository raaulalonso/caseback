// The phone renders of "The app". Each picture is a Blender render of generic phones with real screenshots of the iOS app on
// invented data (tools/app_renders/). The render is transparent, so the black of the site shows through. Under it a row names
// each phone, lined up with where the render puts it (content/app-renders.ts). Every figure says that the data is simulated.
import type { ReactNode } from "react";
import { appRenders } from "@/content/app-renders";
import type { Locale } from "@/lib/i18n";

export type Scene = keyof typeof appRenders;

/** How far under the screen the body of the phone ends, and the shortest hairline worth drawing (both as a fraction of the picture). */
const LEADER_GAP = 0.025;
const MIN_LEADER = 0.015;

export function PhoneFigure({
  scene, lang, label, names, tag, note, eager = false, children,
}: {
  scene: Scene;
  lang: Locale;
  label: string;
  names: Record<string, string>;
  tag: string;
  note: string;
  eager?: boolean;
  children?: ReactNode;
}) {
  const r = appRenders[scene];
  return (
    <figure className="figure phones">
      <div className="phones-stage">
        <img
          className="phones-img"
          src={`/app/${lang}/${scene}.webp`}
          width={r.width}
          height={r.height}
          alt={label}
          loading={eager ? "eager" : "lazy"}
          decoding="async"
        />
        {r.phones.map((p) => {
          // a hairline from the foot of each phone down to its name, like the dimension lines of the rest of the site
          const top = p.bottom + LEADER_GAP;
          return top < 1 - MIN_LEADER ? (
            <span
              key={p.shot}
              className="phones-leader"
              aria-hidden="true"
              style={{ left: `${(p.x * 100).toFixed(2)}%`, top: `${(top * 100).toFixed(2)}%`, height: `${((1 - top) * 100).toFixed(2)}%` }}
            />
          ) : null;
        })}
      </div>
      <ul className="phones-names">
        {r.phones.map((p) => (
          <li key={p.shot} style={{ left: `${(p.x * 100).toFixed(2)}%` }}>{names[p.shot]}</li>
        ))}
      </ul>
      {children}
      <figcaption>
        <span><strong>{tag}</strong> {note}</span>
      </figcaption>
    </figure>
  );
}
