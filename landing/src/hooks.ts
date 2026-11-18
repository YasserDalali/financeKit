import { useEffect, type CSSProperties } from 'react';
import Lenis from 'lenis';

export const prefersReducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Weighted smooth scroll; in-page anchors scroll through Lenis too. Off for reduced motion. */
export function useSmoothScroll() {
  useEffect(() => {
    if (prefersReducedMotion()) return;
    const lenis = new Lenis({ lerp: 0.1 });
    let id = 0;
    const raf = (t: number) => { lenis.raf(t); id = requestAnimationFrame(raf); };
    id = requestAnimationFrame(raf);
    const onClick = (e: MouseEvent) => {
      const a = (e.target as Element).closest<HTMLAnchorElement>('a[href^="#"]');
      const el = a && document.querySelector(a.getAttribute('href')!);
      if (el) { e.preventDefault(); lenis.scrollTo(el as HTMLElement); }
    };
    document.addEventListener('click', onClick);
    return () => { cancelAnimationFrame(id); document.removeEventListener('click', onClick); lenis.destroy(); };
  }, []);
}

/** One-shot reveals: adds .in to [data-reveal], [data-rule] and [data-split] as they enter the viewport. */
export function useReveal() {
  useEffect(() => {
    const io = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
    }), { threshold: 0.2, rootMargin: '0px 0px -8% 0px' });
    document.querySelectorAll('[data-reveal], [data-rule], [data-split]').forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
}

/** Sets the CSS stagger delay for the i-th item of a group. */
export const stagger = (i: number, step = 0.08) => ({ '--d': `${i * step}s` }) as CSSProperties;

/** Shared title type: Phonic, tight tracking. Size is set per section. */
export const title = 'm-0 font-sans font-medium leading-[1.02] tracking-[-0.035em] text-balance';
export const titleSize = 'text-[clamp(2.25rem,5.2vw,5rem)]';
