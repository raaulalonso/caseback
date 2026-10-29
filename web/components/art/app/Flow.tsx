// Where the data goes: the disc sends it to the phone over Bluetooth and from the phone it can go to Apple Health or to a file.
// There is nothing else in the drawing on purpose: no account and no server. Wide and narrow versions, same layout.
import type { Dict } from "@/lib/i18n";
import { ArtFrame } from "../ArtFrame";

type T = Dict["app"]["art"]["data"]["flow"];

type Geo = { w: number; h: number; cls: string; disc: number; lineEnd: number; phone: number; fork: number; end: number; label: number; cy: number; up: number; down: number };
const WIDE: Geo = { w: 640, h: 104, cls: "only-wide", disc: 24, lineEnd: 232, phone: 240, fork: 330, end: 466, label: 482, cy: 46, up: 22, down: 70 };
const NARROW: Geo = { w: 360, h: 118, cls: "only-narrow", disc: 18, lineEnd: 118, phone: 126, fork: 190, end: 238, label: 250, cy: 54, up: 30, down: 78 };

const PHONE_W = 34;
const PHONE_H = 62;

/** An arrowhead whose tip is at (x, y), pointing right. */
const head = (x: number, y: number) => `M${x - 6} ${y - 4.5} L${x} ${y} L${x - 6} ${y + 4.5}`;

function FlowDrawing({ t, g }: { t: T; g: Geo }) {
  const { w, h, cy, up, down } = g;
  const px = g.phone + PHONE_W / 2;
  return (
    <ArtFrame w={w} h={h} label={t.label} className={`art-flow ${g.cls}`}>
      {/* the disc */}
      <circle className="ln w15" cx={g.disc} cy={cy} r={16} />
      <text x={g.disc} y={h - 8} textAnchor="middle">{t.disc}</text>

      {/* Bluetooth */}
      <path className="ln w15" d={`M${g.disc + 16} ${cy} H${g.lineEnd} ${head(g.lineEnd, cy)}`} />
      <text x={(g.disc + 16 + g.lineEnd) / 2} y={cy - 10} textAnchor="middle">{t.bluetooth}</text>

      {/* the phone */}
      <rect className="ln w15" x={g.phone} y={cy - PHONE_H / 2} width={PHONE_W} height={PHONE_H} rx={8} />
      <path className="ln w075 dim" d={`M${px - 6} ${cy - PHONE_H / 2 + 6} H${px + 6}`} />
      <text x={px} y={h - 8} textAnchor="middle">{t.phone}</text>

      {/* what the phone can send out: Apple Health and a file */}
      <path
        className="ln w15"
        d={`M${g.phone + PHONE_W} ${cy} H${g.fork} M${g.fork} ${up} V${down} M${g.fork} ${up} H${g.end} ${head(g.end, up)} M${g.fork} ${down} H${g.end} ${head(g.end, down)}`}
      />
      <text className="strong" x={g.label} y={up} dy="0.34em">{t.health}</text>
      <text className="strong" x={g.label} y={down} dy="0.34em">{t.file}</text>
    </ArtFrame>
  );
}

export function FlowArt({ t }: { t: T }) {
  return (
    <>
      <FlowDrawing t={t} g={WIDE} />
      <FlowDrawing t={t} g={NARROW} />
    </>
  );
}
