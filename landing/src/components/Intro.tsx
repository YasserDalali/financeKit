import { useEffect, useRef, useState } from 'react';
import LogoMark from './Logo';

type Props = {
  /** real load progress, 0–1 */
  progress: number;
  /** true once loaded and the counter has reached 100 */
  onFull: () => void;
  /** true while the overlay is wiping away */
  leaving: boolean;
  /** overlay has finished leaving */
  onGone: () => void;
};

/** Full-screen intro: logo, a hairline loading bar and a counter. Wipes upward once everything is loaded. */
export default function Intro({ progress, onFull, leaving, onGone }: Props) {
  const [shown, setShown] = useState(0); // displayed value, eased toward the real progress so it never jumps
  const target = useRef(0);
  target.current = progress;
  const fired = useRef(false);

  useEffect(() => {
    let id = 0, last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000); last = now;
      setShown((s) => {
        const goal = target.current;
        const next = s + (goal - s) * (1 - Math.exp(-dt * 7)) + dt * 0.05; // ease + a small constant push so it always finishes
        return Math.min(goal, next);
      });
      id = requestAnimationFrame(tick);
    };
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
  }, []);

  // reduced-motion kills transitions (no transitionend), so don't rely on it alone
  useEffect(() => {
    if (!leaving) return;
    const t = setTimeout(onGone, 1000);
    return () => clearTimeout(t);
  }, [leaving, onGone]);

  const pct = Math.min(100, Math.round(shown * 100));
  useEffect(() => {
    if (!fired.current && progress >= 1 && shown >= 0.995) { fired.current = true; onFull(); }
  }, [progress, shown, onFull]);

  return (
    <div
      role="progressbar" aria-label="Loading" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}
      onTransitionEnd={(e) => { if (leaving && e.target === e.currentTarget && e.propertyName === 'translate') onGone(); }}
      className={`fixed inset-0 z-[100] flex flex-col justify-between bg-blue-600 p-[var(--gutter)] text-white transition-[translate] duration-[900ms] ease-io ${leaving ? '-translate-y-full' : ''}`}
    >
      <div aria-hidden="true" />
      {/* big mark in the middle: outlined while loading, fills in solid as the bar advances */}
      <div className="absolute inset-0 grid place-items-center">
        <div className="relative size-[clamp(120px,22vw,300px)]">
          <LogoMark className="absolute inset-0 size-full text-white/18" />
          <LogoMark className="absolute inset-0 size-full text-white" style={{ clipPath: `inset(${(1 - shown) * 100}% 0 0 0)` }} />
        </div>
      </div>
      <div>
        <div className="mb-4 flex items-end justify-between text-xs tracking-[.14em] text-white/70 uppercase">
          <span>Loading</span>
          <span className="text-[clamp(2.5rem,6vw,5rem)] leading-none font-medium tracking-[-0.03em] text-white tabular-nums normal-case">{String(pct).padStart(3, '0')}</span>
        </div>
        <div className="h-px w-full bg-white/25">
          <div className="h-full origin-left bg-white" style={{ transform: `scaleX(${shown})` }} />
        </div>
      </div>
    </div>
  );
}
