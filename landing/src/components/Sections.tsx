import { stagger, title, titleSize } from '../hooks';

/** Hairline section divider; draws in from the left when it enters the viewport. */
export const Rule = () => <hr data-rule className="rule" />;

/** Big centered statement above the glass ribbon. On desktop it fills the viewport and stays in the quiet top. */
export function Exposure() {
  return (
    <section className="bg-mist bg-[url(/assets/wave.jpg)] bg-size-[200%_auto] bg-position-[55%_bottom] bg-no-repeat pt-28 pb-[52vw] text-center lg:flex lg:min-h-svh lg:items-center lg:justify-center lg:bg-cover lg:bg-position-[center_bottom] lg:pt-[6vh] lg:pb-[40vh]">
      <div className="px-gutter">
        <h2 data-reveal className={`${title} mx-auto max-w-[13ch] text-[clamp(2.75rem,11vw,4.5rem)] text-ink lg:max-w-[15ch] lg:text-[min(6.8vw,11vh)] lg:leading-[.98]`}>
          Ten holdings is not diversification.
        </h2>
        <p data-reveal className="mx-auto mt-6 max-w-[40ch] text-[clamp(1.0625rem,1.2vw,1.25rem)] leading-[1.55] text-muted lg:mt-[2.4vh] lg:max-w-[44ch] lg:text-[max(1rem,min(1.55vw,2.4vh))]">
          Overlapping ETFs, correlated assets and sector concentration hide in plain sight. FinRisk shows what you actually hold.
        </p>
      </div>
    </section>
  );
}

const caps = [
  { icon: 'icon-1', name: 'Portfolio risk', text: 'Overlap, concentration and drawdown — your real exposure.' },
  { icon: 'icon-2', name: 'Stress testing', text: 'Recessions, rate shocks and supply disruptions, before they happen.' },
  { icon: 'icon-3', name: 'Intrinsic value', text: 'DCF, dividend models and multiples weigh price against worth.' },
  { icon: 'icon-4', name: 'Fundamentals', text: 'Statements, cash flow and balance-sheet health, step by step.' },
];

/** Black band, white line-art icons in a 2×2 grid; icons sit dimmed until hovered. */
export function Capabilities() {
  return (
    <section className="bg-night py-[clamp(72px,8vh,120px)] text-white lg:flex lg:min-h-svh lg:items-center">
      <div className="w-full px-gutter">
        <h2 data-reveal className={`${title} ${titleSize} mx-auto max-w-[14ch] text-center`}>Risk, from every side.</h2>
        <ul className="mx-auto mt-[clamp(32px,5vh,72px)] grid max-w-[1000px] grid-cols-2 gap-x-[clamp(32px,6vw,96px)] gap-y-[clamp(32px,4vh,64px)] text-center max-sm:gap-x-4 max-sm:gap-y-12">
          {caps.map((c, i) => (
            <li key={c.icon} data-reveal style={stagger(i)} className="group">
              <img
                src={`/assets/${c.icon}.png`} alt="" width={512} height={512} loading="lazy"
                className="mx-auto mb-4 aspect-square w-full max-w-[min(176px,16vh)] object-contain opacity-30 transition-[opacity,translate] duration-700 ease-expo group-hover:-translate-y-2 group-hover:opacity-100 touch:opacity-90"
              />
              <h3 className="text-xl font-medium tracking-[-0.01em]">{c.name}</h3>
              <p className="mx-auto mt-2 max-w-[34ch] text-base leading-normal text-white/55 transition-colors duration-[600ms] ease-expo group-hover:text-white/85 max-sm:text-sm">{c.text}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/** Blue CTA with a blueprint grid fading from the top-right corner. */
export function Cta() {
  return (
    <section id="access" className="relative overflow-hidden bg-blue-600 pt-[clamp(112px,14vw,220px)] pb-[clamp(80px,9vw,140px)] text-white">
      <div className="blueprint" aria-hidden="true" />
      <div className="relative flex flex-wrap items-end justify-between gap-8 px-gutter">
        <h2 data-reveal className={`${title} max-w-[11ch] text-[clamp(2.75rem,7vw,7rem)]`}>Prepare for uncertainty.</h2>
        {/* TODO: placeholder address — replace with the real inbox or a sign-up form */}
        <a
          data-reveal href="mailto:hello@finrisk.app"
          className="group relative inline-flex items-center gap-6 overflow-hidden bg-white px-7 py-[22px] text-[1.0625rem] font-medium tracking-[-0.01em] text-blue-600 before:absolute before:inset-0 before:translate-y-[101%] before:bg-ink before:transition-transform before:duration-[600ms] before:ease-expo hover:before:translate-y-0"
        >
          <span className="relative transition-colors duration-[600ms] ease-expo group-hover:text-white">Request early access</span>
          <span aria-hidden="true" className="relative transition-[color,translate] duration-[600ms] ease-expo group-hover:translate-x-1.5 group-hover:text-white">→</span>
        </a>
      </div>
    </section>
  );
}

/** Continuation of the blue field: links, disclaimer, and the giant serif wordmark. */
export function Footer() {
  const head = 'mb-4 text-xs leading-none font-medium tracking-[.12em] text-white/55 uppercase';
  const link = 'block w-fit py-1 text-white hover:underline';
  return (
    <footer className="overflow-hidden border-t border-white/18 bg-blue-600 text-white">
      <div className="grid grid-cols-[1fr_1fr_2fr] gap-8 px-gutter pt-12 pb-16 max-lg:grid-cols-2">
        <nav aria-label="Product"><h4 className={head}>Product</h4><a className={link} href="#">Portfolio risk</a><a className={link} href="#">Valuation</a><a className={link} href="#">Stress tests</a></nav>
        <nav aria-label="Company"><h4 className={head}>Company</h4><a className={link} href="#">About</a><a className={link} href="#">Contact</a></nav>
        <p className="m-0 max-w-[36ch] justify-self-end text-sm text-white/60 max-lg:col-span-full max-lg:justify-self-start">
          FinRisk provides analysis, not investment advice. Past performance does not guarantee future results.
        </p>
      </div>
      <div data-split aria-hidden="true" className="-mb-[.07em] text-center font-serif text-[40vw] leading-[.78] tracking-[-0.05em]">
        <span className="line"><span>FinRisk</span></span>
      </div>
    </footer>
  );
}
