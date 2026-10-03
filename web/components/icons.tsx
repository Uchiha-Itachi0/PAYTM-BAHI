/**
 * Flat line icons, drawn to Paytm's weight. Deliberately not imitations of
 * Paytm's illustrated icons: a clean line icon is honest for a prototype, and a
 * bad copy of theirs would look worse than none.
 */

type IconProps = { className?: string };

function Svg({
  className,
  children,
}: IconProps & { children: React.ReactNode }): React.ReactElement {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      {children}
    </svg>
  );
}

export const Search = (p: IconProps): React.ReactElement => (
  <Svg {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="M20 20l-4-4" />
  </Svg>
);

export const Bell = (p: IconProps): React.ReactElement => (
  <Svg {...p}>
    <path d="M18 8a6 6 0 10-12 0c0 7-3 8-3 8h18s-3-1-3-8" />
    <path d="M13.7 21a2 2 0 01-3.4 0" />
  </Svg>
);

export const Mic = (p: IconProps): React.ReactElement => (
  <Svg {...p}>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5 11a7 7 0 0014 0M12 18v3" />
  </Svg>
);

export const Scan = (p: IconProps): React.ReactElement => (
  <Svg {...p}>
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="3" width="7" height="7" rx="1.5" />
    <rect x="3" y="14" width="7" height="7" rx="1.5" />
    <path d="M14 14h3v3M21 21v.01M17 21h.01M21 17h.01" />
  </Svg>
);

export const Mobile = (p: IconProps): React.ReactElement => (
  <Svg {...p}>
    <rect x="6" y="2" width="12" height="20" rx="2.5" />
    <path d="M11 18h2" />
  </Svg>
);

export const Bank = (p: IconProps): React.ReactElement => (
  <Svg {...p}>
    <path d="M3 10h18M5 10v8M19 10v8M9 10v8M15 10v8M3 18h18M12 3l9 5H3z" />
  </Svg>
);

export const Book = (p: IconProps): React.ReactElement => (
  <Svg {...p}>
    <path d="M6 3h11a2 2 0 012 2v16H8a2 2 0 01-2-2z" />
    <path d="M6 17a2 2 0 012-2h11M10 7h5M10 10h3" />
  </Svg>
);

export const Person = (p: IconProps): React.ReactElement => (
  <Svg {...p}>
    <circle cx="12" cy="8" r="3.5" />
    <path d="M5 20c0-3.5 3-6 7-6s7 2.5 7 6" />
  </Svg>
);

export const Check = (p: IconProps): React.ReactElement => (
  <Svg {...p}>
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </Svg>
);

export const Moon = (p: IconProps): React.ReactElement => (
  <Svg {...p}>
    <path d="M20 14.5A8 8 0 019.5 4a8 8 0 1010.5 10.5z" />
  </Svg>
);

export const Chat = (p: IconProps): React.ReactElement => (
  <Svg {...p}>
    <path d="M4 5h16v11H9l-5 4z" />
  </Svg>
);

export const Plus = (p: IconProps): React.ReactElement => (
  <Svg {...p}>
    <path d="M12 5v14M5 12h14" />
  </Svg>
);
