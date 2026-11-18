/** FinRisk mark: solid half = what you own, offset translucent half = what you risk. Uses currentColor. */
export default function LogoMark({ className = '' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 32 32" width="26" height="26" aria-hidden="true">
      <path d="M0 0H32L0 32Z" fill="currentColor" />
      <path d="M32 6V32H6Z" fill="currentColor" opacity=".45" />
    </svg>
  );
}
