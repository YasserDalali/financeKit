import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { src } from '../assets';

/** Full-screen looping cube (2.5s clip played forward then back), grainy serif title, scroll cue. */
export default function Hero({ started }: { started: boolean }) {
  const video = useRef<HTMLVideoElement>(null);
  // the clip starts with the rest of the page animations, once the intro is gone
  useEffect(() => { if (started) video.current?.play().catch(() => {}); }, [started]);
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(scrollY > 40);
    addEventListener('scroll', onScroll, { passive: true });
    return () => removeEventListener('scroll', onScroll);
  }, []);

  return (
    <section id="hero" className="relative h-svh min-h-[560px] overflow-hidden bg-hero text-white">
      <video
        ref={video} className="absolute inset-0 size-full object-cover"
        src={src('/assets/hero-loop.mp4')} poster="/assets/hero-poster.jpg"
        muted loop playsInline preload="auto" aria-hidden="true"
      />
      <div className="absolute inset-x-0 bottom-0 flex items-end justify-between gap-8 px-gutter pb-[clamp(28px,5vw,64px)] max-lg:flex-col max-lg:items-start">
        <h1 data-split className="font-serif text-[clamp(3.5rem,11vw,11.5rem)] leading-[.88] font-normal tracking-[-0.03em] italic">
          <span className="line"><span className="grain-text">Know</span></span>
          <span className="line"><span className="grain-text">what you own.</span></span>
        </h1>
        <p data-reveal style={{ '--d': '.45s' } as CSSProperties} className="m-0 max-w-[30ch] text-[clamp(1rem,1.15vw,1.1875rem)] leading-normal text-white/88">
          Understand what you risk. Portfolio risk, intrinsic value and macro exposure — in one calm terminal.
        </p>
      </div>
      <div
        aria-hidden="true"
        className={`absolute top-1/2 right-[var(--gutter)] grid -translate-y-1/2 justify-items-center gap-2.5 text-xs tracking-[.14em] text-white/80 uppercase transition-opacity duration-500 ease-expo max-lg:hidden ${scrolled ? 'opacity-0' : ''}`}
      >
        <span>Scroll</span>
        <i className="relative h-14 w-px overflow-hidden bg-white/30 after:absolute after:top-0 after:left-0 after:h-[40%] after:w-px after:animate-cue after:bg-white" />
      </div>
    </section>
  );
}
