import Link from "next/link";

/**
 * Paytm's 4-across grid of icon tiles (Scan & Pay, To Mobile…). Solid navy
 * tiles with white line icons, a short label under each.
 */
export interface Tile {
  label: string;
  icon: React.ReactNode;
  href?: string;
  /** A count on the tile's corner: unread messages. */
  badge?: number;
}

export function TileGrid({ tiles }: { tiles: Tile[] }): React.ReactElement {
  return (
    <div className="grid grid-cols-4 gap-[9px]">
      {tiles.map((t) => {
        const body = (
          <>
            <span className="relative mb-1.5 grid h-[52px] place-items-center rounded-tile bg-navy text-white [&_svg]:size-[23px]">
              {t.icon}
              {t.badge ? (
                <span className="absolute -right-1 -top-1 grid min-w-5 place-items-center rounded-full bg-cyan px-1 text-[11px] font-extrabold leading-5 text-white">
                  {t.badge}
                </span>
              ) : null}
            </span>
            <span className="block text-[10.5px] font-semibold leading-tight">
              {t.label}
            </span>
          </>
        );
        return t.href ? (
          <Link key={t.label} href={t.href} className="text-center">
            {body}
          </Link>
        ) : (
          <div key={t.label} className="text-center">
            {body}
          </div>
        );
      })}
    </div>
  );
}
