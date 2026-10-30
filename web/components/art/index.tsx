// The drawing of each plate. "How it's worn" is 3D (wear/WearArt.tsx); the others are drawn in SVG.
import type { ReactNode } from "react";
import type { Dict, Locale, Section } from "@/lib/i18n";
import { SenseArt } from "./measure/Sense";
import { SignalsArt } from "./measure/Signals";
import { FlowArt } from "./app/Flow";
import { PhoneFigure } from "./app/Phones";
import { MapArt } from "./open/Map";
import { TermsArt } from "./open/Terms";
import { VerifyArt } from "./open/Verify";
import { WearArt } from "./wear/WearArt";
import type { WearKind } from "./wear/scenes";

const WEAR: WearKind[] = ["caseback", "charge", "band"];

export function plateArt(section: Section, index: number, t: Dict, lang: Locale): ReactNode {
  if (section === "wear") {
    const a = t.wear.plates[index]?.art;
    return a ? <WearArt kind={WEAR[index]} labels={a.labels} label={a.label} /> : null;
  }
  if (section === "measure") {
    const a = t.measure.art;
    return [<SenseArt key="s" t={a.sense} />, <SignalsArt key="g" t={a.signals} />][index] ?? null;
  }
  if (section === "app") {
    const a = t.app.art;
    const common = { lang, tag: a.tag, note: a.note };
    return [
      <PhoneFigure key="t" scene="today" label={a.today.label} names={a.today.names} eager {...common} />,
      <PhoneFigure key="r" scene="trends" label={a.trends.label} names={a.trends.names} {...common} />,
      <PhoneFigure key="d" scene="device" label={a.data.label} names={a.data.names} {...common}>
        <FlowArt t={a.data.flow} />
      </PhoneFigure>,
      <PhoneFigure key="w" scene="widgets" label={a.widgets.label} names={a.widgets.names} {...common} note={a.widgets.note} />,
    ][index] ?? null;
  }
  if (section === "open") {
    const a = t.open.art;
    return [<MapArt key="m" t={a.map} />, <TermsArt key="t" t={a.terms} />, <VerifyArt key="v" t={a.verify} />][index] ?? null;
  }
  return null;
}
