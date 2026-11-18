import { useEffect, useRef } from 'react';
import { stagger, title, titleSize } from '../hooks';

const principles = [
  ['Capital preservation before appreciation.', 'Drawdown, volatility and downside capture show what you could lose before what you could gain.'],
  ['Fundamentals before speculation.', 'Statements, profitability, cash flow and balance-sheet health in one view.'],
  ['Exposure, not the number of holdings.', 'Look through every ETF to the holdings, sectors and correlations underneath.'],
  ['Intrinsic value over market excitement.', 'DCF, dividend discount, P/E, P/S, EV/EBITDA and Peter Lynch fair value.'],
  ['Conviction over short-term noise.', 'Stress tests separate temporary volatility from fundamental deterioration.'],
];

/**
 * Principles on the left; on desktop the helix clip on the right is scrubbed by scroll position.
 * Phones get the still image and never download the clip.
 */
export default function Philosophy() {
  const section = useRef<HTMLElement>(null);
  const video = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (matchMedia('(max-width: 767px)').matches) return;
    const el = section.current!, v = video.current!;
    let url = '';
    // In-memory copy: seeking is instant and works even on hosts without range requests
    fetch('/assets/helix-scrub.mp4').then((r) => r.blob()).then((b) => { url = URL.createObjectURL(b); v.preload = 'auto'; v.src = url; }).catch(() => {});
    let cur = 0, id = 0;
    const tick = () => {
      const r = el.getBoundingClientRect();
      const target = Math.min(1, Math.max(0, (innerHeight - r.top) / (innerHeight + r.height))); // 0 entering → 1 leaving
      cur += (target - cur) * 0.12;
      if (v.duration && Math.abs(v.currentTime - cur * v.duration) > 0.01) v.currentTime = cur * v.duration;
      id = requestAnimationFrame(tick);
    };
    id = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(id); if (url) URL.revokeObjectURL(url); };
  }, []);

  return (
    <section
      ref={section}
      id="philosophy"
      className="relative flex min-h-[clamp(600px,56vw,1000px)] items-center overflow-hidden bg-haze lg:min-h-svh max-lg:items-start max-lg:pt-24 max-md:bg-[#e5e5ef] max-md:bg-[url(/assets/ribbon.jpg)] max-md:bg-cover max-md:bg-position-[78%_center] max-md:bg-no-repeat max-sm:bg-size-[220%_auto] max-sm:bg-position-[92%_bottom] max-sm:pb-[100vw]"
    >
      <video
        ref={video}
        poster="/assets/helix-poster.jpg" muted playsInline preload="none" aria-hidden="true"
        className="pointer-events-none absolute inset-0 size-full object-cover object-right max-lg:object-[78%_center] max-md:hidden"
      />
      <div className="relative w-full px-gutter">
        <div className="max-w-[560px] max-lg:max-w-[62%] max-sm:max-w-full">
          <h2 data-reveal className={`${title} ${titleSize} text-ink`}>Clarity over speculation.</h2>
          <ol className="mt-12">
            {principles.map(([head, more], i) => (
              // hover (or keyboard focus) opens the feature behind each principle; always open on touch
              <li
                key={head} data-reveal tabIndex={0} style={stagger(i)}
                className="group grid grid-cols-[auto_1fr] gap-x-6 border-t border-ink/14 py-4 text-[1.0625rem] text-ink outline-none focus-visible:shadow-[inset_2px_0_0_var(--color-blue-600)]"
              >
                <span className="row-span-2 pt-[.3em] text-xs text-blue-600 tabular-nums">{String(i + 1).padStart(2, '0')}</span>
                <span className="transition-transform duration-[600ms] ease-expo group-hover:translate-x-1.5 group-focus-visible:translate-x-1.5">{head}</span>
                <span className="grid grid-rows-[0fr] transition-[grid-template-rows] duration-[600ms] ease-expo group-hover:grid-rows-[1fr] group-focus-visible:grid-rows-[1fr] touch:grid-rows-[1fr]">
                  <span className="overflow-hidden text-sm leading-normal text-muted opacity-0 transition-[opacity,padding] duration-500 ease-expo group-hover:pt-2 group-hover:opacity-100 group-focus-visible:pt-2 group-focus-visible:opacity-100 touch:pt-2 touch:opacity-100">
                    {more}
                  </span>
                </span>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
