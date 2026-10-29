// Plate 1: the disc on the skin, the light that goes in from three LEDs and comes back to the photodiode, and what the
// photodiode reads. Hand-drawn SVG, still. Real data: eight seconds of finger PPG from BIDMC (see
// tools/web_measure_data.py). One drawing for every width: the names that do not fit the picture are in the key below.
import { measureData } from "@/content/measure-data";
import { r2 } from "@/components/home/geometry";
import type { Dict } from "@/lib/i18n";
import { ArtFrame } from "../ArtFrame";

type T = Dict["measure"]["art"]["sense"];

const X0 = 110;
const W = 640;
const DL = 130; // disc and skin share these edges
const DR = 730;
const CX = (DL + DR) / 2;
const TOP = 8;
const FACE = 84; // the face of the disc is the surface of the skin
const SKIN_BOT = FACE + 190;

// Three LEDs and the photodiode on the face, centred on the disc.
const PD = CX + 140;
const LEDS = [
  { key: "ir", x: PD - 280, color: "#e8e8e8", dash: true, end: PD - 14, depth: 150 },
  { key: "red", x: PD - 200, color: "#FF4D3D", dash: false, end: PD, depth: 110 },
  { key: "green", x: PD - 120, color: "#3DDC84", dash: false, end: PD + 14, depth: 66 },
] as const;

const hatch = Array.from({ length: 44 }, (_, i) => {
  const x = DL - 200 + i * 18;
  return `M${x} ${SKIN_BOT} L${x + 200} ${FACE}`;
}).join(" ");

// Eight seconds of PPG, every second sample.
const ppg = measureData.ppg;
const PY0 = SKIN_BOT + 62, PY1 = PY0 + 86, AXIS = PY1 + 20;
const pts = ppg.samples.filter((_, i) => i % 2 === 0);
const trace = pts.map((v, i) => `${i ? "L" : "M"}${r2(DL + (i / (pts.length - 1)) * (DR - DL))} ${r2(PY1 - v * (PY1 - PY0))}`).join(" ");
const H = AXIS + 38;

export function SenseArt({ t }: { t: T }) {
  const ledMid = (LEDS[0].x + LEDS[2].x) / 2;
  return (
    <figure className="figure">
      <ArtFrame w={W} h={H} x0={X0} label={t.label} className="art-sense">
        <defs>
          <clipPath id="skin-clip"><rect x={DL} y={FACE} width={DR - DL} height={SKIN_BOT - FACE} /></clipPath>
        </defs>

        {/* skin */}
        <g clipPath="url(#skin-clip)">
          <path className="hatch" d={hatch} opacity={0.32} />
        </g>
        <path className="ln w075 dim" d={`M${DL} ${FACE} V${SKIN_BOT} H${DR} V${FACE}`} />
        <text className="halo" x={DL + 20} y={SKIN_BOT - 22} dy="0.34em">{t.skin}</text>

        {/* the disc */}
        <rect className="ln w15" x={DL} y={TOP} width={DR - DL} height={FACE - TOP} rx={16} fill="#000" />
        <text x={DL + 28} y={FACE - 44}>{t.disc}</text>

        {/* LEDs and photodiode on its face */}
        {LEDS.map((l) => (
          <rect key={l.key} className="ln w15" x={l.x - 12} y={FACE - 7} width={24} height={14} fill="#000" strokeDasharray={l.dash ? "3 3" : undefined} style={{ stroke: l.color }} />
        ))}
        <rect className="ln w15" x={PD - 28} y={FACE - 7} width={56} height={14} fill="#000" />
        <rect className="ln w075 dim" x={PD - 12} y={FACE - 2.5} width={24} height={5} />

        {/* names over them */}
        <path className="ln w075" d={`M${LEDS[0].x} ${FACE - 24} V${FACE - 30} H${LEDS[2].x} V${FACE - 24}`} />
        <text x={ledMid} y={FACE - 44} textAnchor="middle">{t.leds}</text>
        <line className="ln w075" x1={PD} y1={FACE - 30} x2={PD} y2={FACE - 24} />
        <text x={PD} y={FACE - 44} textAnchor="middle">{t.pd}</text>

        {/* the light: out of each LED, through the skin, back to the photodiode */}
        {LEDS.map((l) => (
          <g key={l.key}>
            <path
              className="ln w15"
              d={`M${l.x} ${FACE + 7} A${(l.end - l.x) / 2} ${l.depth} 0 0 0 ${l.end} ${FACE + 7}`}
              strokeDasharray={l.dash ? "5 5" : undefined}
              style={{ stroke: l.color }}
            />
            <path className="ln w15" d={`M${l.end - 5} ${FACE + 16} L${l.end} ${FACE + 9} L${l.end + 5} ${FACE + 16}`} style={{ stroke: l.color }} />
          </g>
        ))}

        {/* what the photodiode reads */}
        <text x={DL} y={PY0 - 20}>{t.ppgTitle}</text>
        <path className="ln w15" d={trace} style={{ stroke: "var(--ink-2)" }} />
        <line className="ln w075 dim" x1={DL} y1={AXIS} x2={DR} y2={AXIS} />
        <line className="ln w075 dim" x1={DL} y1={AXIS} x2={DL} y2={AXIS + 6} />
        <line className="ln w075 dim" x1={DR} y1={AXIS} x2={DR} y2={AXIS + 6} />
        <text className="mono axis" x={DL} y={AXIS + 24}>0</text>
        <text className="mono axis" x={DR} y={AXIS + 24} textAnchor="end">8 {t.seconds}</text>
      </ArtFrame>

      <ul className="lights">
        <li><i className="swatch" style={{ borderColor: "#3DDC84" }} />{t.green}</li>
        <li><i className="swatch" style={{ borderColor: "#FF4D3D" }} />{t.red}</li>
        <li><i className="swatch dashed" style={{ borderColor: "#e8e8e8" }} />{t.ir}</li>
      </ul>
      <figcaption>
        <span>{t.note}</span>
        <span>{t.source}</span>
      </figcaption>
    </figure>
  );
}
