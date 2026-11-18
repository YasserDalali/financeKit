import { useEffect, useRef, useState } from 'react';
import LogoMark from './Logo';

type Mode = 'top' | 'hidden' | 'solid';

/** Transparent over the hero, tucked away before the hero title reaches it, solid pill once the hero is gone. */
export default function Nav() {
  const ref = useRef<HTMLElement>(null);
  const [mode, setMode] = useState<Mode>('top');

  useEffect(() => {
    const nav = ref.current!;
    const hero = document.getElementById('hero')!;
    const heroTitle = hero.querySelector<HTMLElement>('h1')!;
    const navH = nav.offsetHeight; // measured once: the pill is shorter, and a changing threshold would flicker
    let frame = 0;
    const update = () => {
      frame = 0;
      const y = scrollY;
      const titleTop = hero.offsetTop + heroTitle.parentElement!.offsetTop + heroTitle.offsetTop;
      if (y > hero.offsetTop + hero.offsetHeight - navH) setMode('solid');
      else setMode(y > titleTop - navH * 2.5 ? 'hidden' : 'top');
    };
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(update); };
    update();
    addEventListener('scroll', onScroll, { passive: true });
    return () => { removeEventListener('scroll', onScroll); cancelAnimationFrame(frame); };
  }, []);

  const solid = mode === 'solid';
  return (
    <header
      ref={ref}
      className={`fixed z-30 flex items-center justify-between transition-[background-color,color,translate] duration-500 ease-expo ${
        solid
          ? 'top-3 left-1/2 w-[min(720px,calc(100vw-24px))] -translate-x-1/2 animate-nav-in rounded-full border border-ink/8 bg-white py-2 pr-2 pl-5 text-ink shadow-[0_8px_30px_rgba(0,10,102,.10)]'
          : `inset-x-0 top-0 px-gutter py-[18px] text-white ${mode === 'hidden' ? '-translate-y-full' : ''}`
      }`}
    >
      <a href="#top" aria-label="FinRisk home" className={`group flex items-center font-semibold tracking-[-0.03em] ${solid ? 'gap-2.5 text-[1.0625rem]' : 'gap-3 text-xl'}`}>
        <LogoMark className={`transition-[rotate,color] duration-700 ease-expo group-hover:-rotate-90 ${solid ? 'size-5 text-blue-600' : ''}`} />
        <span>FinRisk</span>
      </a>
      <a
        href="#access"
        className={
          solid
            ? 'rounded-full bg-ink px-4 py-[9px] text-sm text-white transition-colors duration-[400ms] ease-expo hover:bg-blue-600'
            : 'relative text-sm after:absolute after:inset-x-0 after:-bottom-[3px] after:h-px after:origin-right after:scale-x-0 after:bg-current after:transition-transform after:duration-500 after:ease-expo hover:after:origin-left hover:after:scale-x-100'
        }
      >
        Request access
      </a>
    </header>
  );
}
