import type { CSSProperties } from 'react';

/** FinRisk mark: solid half = what you own, offset translucent half = what you risk. Uses currentColor. */
export default function LogoMark({ className = '', style }: { className?: string; style?: CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 32 32" aria-hidden="true">
      <path d="M0 0H32L0 32Z" fill="currentColor" />
      <path d="M32 6V32H6Z" fill="currentColor" opacity=".45" />
    </svg>
  );
}
