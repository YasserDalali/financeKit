import { useCallback, useEffect, useState } from 'react';
import { preload } from './assets';
import { useReveal, useSmoothScroll } from './hooks';
import Intro from './components/Intro';
import Nav from './components/Nav';
import Hero from './components/Hero';
import Philosophy from './components/Philosophy';
import Features from './components/Features';
import { Capabilities, Cta, Exposure, Footer, Rule } from './components/Sections';

/** loading → (everything fetched) → leaving (intro wipes away over the finished page) → ready (animations start) */
type Phase = 'loading' | 'leaving' | 'ready';

export default function App() {
  const [phase, setPhase] = useState<Phase>('loading');
  const [progress, setProgress] = useState(0);
  const ready = phase === 'ready';

  useEffect(() => { preload(setProgress); }, []);

  // No scrolling behind the intro
  useEffect(() => {
    document.documentElement.style.overflow = ready ? '' : 'hidden';
    if (!ready) scrollTo(0, 0);
  }, [ready]);

  useSmoothScroll(ready);
  useReveal(ready);

  const onFull = useCallback(() => setPhase('leaving'), []);
  const onGone = useCallback(() => setPhase('ready'), []);

  return (
    <>
      {phase !== 'ready' && <Intro progress={progress} onFull={onFull} leaving={phase === 'leaving'} onGone={onGone} />}
      {/* mounted only once assets are in memory, so every video/image is served instantly */}
      {phase !== 'loading' && (
        <>
          <Nav />
          <main id="top">
            <Hero started={ready} />
            <Rule />
            <Exposure />
            <Rule />
            <Capabilities />
            <Rule />
            <Philosophy />
            <Rule />
            <Features />
            <Cta />
          </main>
          <Footer />
        </>
      )}
    </>
  );
}
