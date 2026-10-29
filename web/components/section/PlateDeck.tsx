"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/** Keeps the plate counter in the corner on the plate that fills most of the screen. Scrolling is left free. */
export function PlateDeck({ children, count, label, of }: { children: ReactNode; count: number; label: string; of: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    const plates = Array.from(ref.current?.querySelectorAll<HTMLElement>(".plate") ?? []);
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) if (e.isIntersecting) setCurrent(plates.indexOf(e.target as HTMLElement));
      },
      { rootMargin: "-45% 0px -45% 0px" },
    );
    plates.forEach((p) => io.observe(p));
    return () => io.disconnect();
  }, []);

  const go = (i: number) => {
    const plates = ref.current?.querySelectorAll<HTMLElement>(".plate");
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    plates?.[i]?.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
  };

  return (
    <div ref={ref} className="deck">
      {children}
      <nav className="plate-index" aria-label={label}>
        {Array.from({ length: count }, (_, i) => (
          <button
            key={i}
            type="button"
            className={i === current ? "on" : undefined}
            aria-current={i === current ? "step" : undefined}
            aria-label={`${label} ${i + 1} ${of} ${count}`}
            onClick={() => go(i)}
          />
        ))}
        <span className="plate-count" aria-hidden>
          {current + 1}/{count}
        </span>
      </nav>
    </div>
  );
}
