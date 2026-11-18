import { useReveal, useSmoothScroll } from './hooks';
import Nav from './components/Nav';
import Hero from './components/Hero';
import Philosophy from './components/Philosophy';
import Features from './components/Features';
import { Capabilities, Cta, Exposure, Footer, Rule } from './components/Sections';

export default function App() {
  useSmoothScroll();
  useReveal();
  return (
    <>
      <Nav />
      <main id="top">
        <Hero />
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
  );
}
