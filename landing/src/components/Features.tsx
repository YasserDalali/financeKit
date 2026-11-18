import { useCallback, useEffect, useRef, useState } from 'react';
import { prefersReducedMotion, title, titleSize } from '../hooks';

const features = [
  { img: 'card-portfolio', name: 'Portfolio risk intelligence', text: 'Composition, concentration, ETF overlap, correlation, beta, volatility and drawdowns.' },
  { img: 'card-fundamentals', name: 'Fundamental analysis', text: 'Financial statements, profitability, cash flow, balance-sheet health and valuation multiples.' },
  { img: 'card-valuation', name: 'Intrinsic valuation', text: 'DCF, dividend discount, comparable P/E and P/S, EV/EBITDA and Peter Lynch fair value.' },
  { img: 'card-stress', name: 'Stress testing', text: 'Recessions, inflation, rate moves, geopolitical, commodity and supply-chain shocks.' },
  { img: 'card-tower', name: 'Market intelligence', text: 'Institutional ownership, insider transactions, analyst consensus and filings.' },
];

const arrow =
  'grid size-12 cursor-pointer place-items-center text-2xl text-ink transition-[color,opacity,translate,scale] duration-200 ease-expo enabled:hover:text-blue-600 enabled:active:scale-[.88] disabled:cursor-default disabled:opacity-25 focus-visible:outline focus-visible:outline-offset-2 focus-visible:outline-blue-600';

/** Title top-left, card carousel on the right: native scroll-snap plus buttons, arrow keys and mouse drag. */
export default function Features() {
  const track = useRef<HTMLUListElement>(null);
  const [atStart, setAtStart] = useState(true);
  const [atEnd, setAtEnd] = useState(false);

  const step = () => {
    const t = track.current!;
    return t.firstElementChild!.getBoundingClientRect().width + parseFloat(getComputedStyle(t).columnGap || '16');
  };

  // Native smooth scrollBy gets cut short (snap + Lenis's rAF loop), so ease scrollLeft by hand
  const slide = useCallback((dir: number) => {
    const t = track.current!;
    const from = t.scrollLeft, to = Math.max(0, Math.min(t.scrollWidth - t.clientWidth, from + dir * step()));
    const t0 = performance.now(), dur = prefersReducedMotion() ? 0 : 700;
    t.style.scrollSnapType = 'none';
    const frame = (now: number) => {
      const k = dur ? Math.min(1, (now - t0) / dur) : 1;
      t.scrollLeft = from + (to - from) * (1 - Math.pow(1 - k, 4)); // quart out
      if (k < 1) requestAnimationFrame(frame); else t.style.scrollSnapType = '';
    };
    requestAnimationFrame(frame);
  }, []);

  useEffect(() => {
    const t = track.current!;
    const sync = () => {
      setAtStart(t.scrollLeft < 4);
      setAtEnd(t.scrollLeft > t.scrollWidth - t.clientWidth - 4);
    };
    // Mouse drag-to-scroll (touch scrolls natively); snaps to the nearest card on release
    let drag: { x: number; left: number; moved: boolean } | null = null;
    const down = (e: PointerEvent) => { if (e.pointerType === 'mouse' && e.button === 0) drag = { x: e.clientX, left: t.scrollLeft, moved: false }; };
    const move = (e: PointerEvent) => {
      if (!drag) return;
      const dx = e.clientX - drag.x;
      if (!drag.moved && Math.abs(dx) > 4) { drag.moved = true; t.classList.add('dragging'); }
      if (drag.moved) t.scrollLeft = drag.left - dx;
    };
    const up = () => {
      if (!drag) return;
      const moved = drag.moved; drag = null;
      if (!moved) return;
      t.classList.remove('dragging');
      const s = step();
      slide((Math.round(t.scrollLeft / s) * s - t.scrollLeft) / s);
    };
    sync();
    t.addEventListener('scroll', sync, { passive: true });
    t.addEventListener('pointerdown', down);
    addEventListener('pointermove', move);
    addEventListener('pointerup', up);
    addEventListener('resize', sync);
    return () => {
      t.removeEventListener('scroll', sync); t.removeEventListener('pointerdown', down);
      removeEventListener('pointermove', move); removeEventListener('pointerup', up); removeEventListener('resize', sync);
    };
  }, [slide]);

  return (
    <section aria-label="Features" className="overflow-hidden bg-white py-[clamp(96px,10vw,160px)] lg:flex lg:min-h-svh lg:items-center">
      <div className="grid w-full grid-cols-[minmax(260px,1fr)_2fr] gap-12 px-gutter max-lg:grid-cols-1">
        <div className="flex flex-col justify-between gap-8 max-lg:flex-row max-lg:items-end max-sm:flex-col max-sm:items-start">
          <h2 data-reveal className={`${title} ${titleSize} max-w-[10ch] text-ink`}>Five lenses on every decision.</h2>
          <div data-reveal className="-ml-3 flex gap-4">
            <button className={`${arrow} enabled:hover:-translate-x-1`} aria-label="Previous feature" disabled={atStart} onClick={() => slide(-1)}>←</button>
            <button className={`${arrow} enabled:hover:translate-x-1`} aria-label="Next feature" disabled={atEnd} onClick={() => slide(1)}>→</button>
          </div>
        </div>
        {/* reaches back into the column gap (--fade) so cards dissolve there instead of hitting a hard edge */}
        <div data-reveal className="relative [--fade:72px] mr-[calc(-1*var(--gutter))] ml-[calc(-1*var(--fade))] min-w-0 max-lg:ml-[calc(-1*var(--fade)-1rem)] max-lg:[--fade:24px]">
          <ul
            ref={track} tabIndex={0} aria-label="Feature cards, use arrow keys to browse"
            onKeyDown={(e) => {
              if (e.key === 'ArrowRight') { e.preventDefault(); slide(1); }
              if (e.key === 'ArrowLeft') { e.preventDefault(); slide(-1); }
            }}
            className="car-track relative -mt-10 -mb-16 flex cursor-grab snap-x snap-mandatory scroll-pl-[calc(var(--fade)+1rem)] gap-4 overflow-x-auto overscroll-x-contain pt-10 pr-[var(--gutter)] pb-16 pl-[calc(var(--fade)+1rem)] outline-none focus-visible:shadow-[inset_0_0_0_2px_var(--color-blue-600)]"
          >
            {features.map((f, i) => (
              <li
                key={f.img}
                className="group flex min-w-0 shrink-0 grow-0 basis-[clamp(260px,24vw,360px)] snap-start flex-col border border-ink/8 bg-[linear-gradient(170deg,rgba(255,255,255,.92),rgba(240,242,255,.78))] text-ink shadow-[inset_0_1px_0_#fff,0_12px_32px_rgba(0,10,102,.06)] transition-[translate,box-shadow,border-color] duration-700 ease-expo hover:-translate-y-1.5 hover:border-blue-600/18 hover:shadow-[inset_0_1px_0_#fff,0_28px_60px_rgba(0,10,102,.14)]"
              >
                <figure className="m-0 aspect-[5/4] overflow-hidden bg-[#e8ebf3]">
                  <img
                    src={`/assets/${f.img}.webp`} alt="" width={640} height={512} loading="lazy" draggable={false}
                    className="size-full scale-[1.02] object-cover saturate-[.85] transition-[scale,filter] duration-[1200ms] ease-expo select-none group-hover:scale-[1.08] group-hover:saturate-100"
                  />
                </figure>
                <div className="relative flex flex-1 flex-col border-t border-ink/6 p-[clamp(18px,1.6vw,26px)] before:absolute before:inset-x-0 before:-top-px before:h-px before:origin-left before:scale-x-0 before:bg-blue-600 before:transition-transform before:duration-[800ms] before:ease-expo group-hover:before:scale-x-100">
                  <span className="text-xs font-semibold tracking-[.1em] text-blue-600 tabular-nums">{String(i + 1).padStart(2, '0')}</span>
                  <h3 className="mt-3 min-h-[2.2em] text-[clamp(1.25rem,1.5vw,1.625rem)] leading-[1.1] font-medium tracking-[-0.025em]">{f.name}</h3>
                  <p className="mt-2 text-sm leading-normal text-muted">{f.text}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
