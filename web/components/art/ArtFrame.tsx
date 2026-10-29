"use client";

import { useEffect, useRef, type ReactNode } from "react";

/**
 * The svg of a plate drawing. It publishes `--px`, drawing units per screen pixel, so line weights and type stay the
 * same size on screen however the drawing is scaled (the same idea as the home).
 */
export function ArtFrame({ w, h, x0 = 0, label, children, className }: { w: number; h: number; x0?: number; label: string; children: ReactNode; className?: string }) {
  const ref = useRef<SVGSVGElement>(null);
  useEffect(() => {
    const svg = ref.current;
    if (!svg) return;
    const ro = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width;
      if (width) svg.style.setProperty("--px", (w / width).toFixed(4));
    });
    ro.observe(svg);
    return () => ro.disconnect();
  }, [w]);
  return (
    <svg ref={ref} className={`art ${className ?? ""}`} viewBox={`${x0} 0 ${w} ${h}`} role="img" aria-label={label}>
      {children}
    </svg>
  );
}
