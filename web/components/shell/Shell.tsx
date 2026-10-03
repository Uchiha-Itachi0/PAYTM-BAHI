import Link from "next/link";

import { Bell, Person, Search } from "@/components/icons";

/**
 * The two app shells. BAHI is not a new app: these are screens inside Paytm for
 * Business (the shopkeeper) and the Paytm app (the customer), so each shell is
 * that app's own frame: the sky ground, its top bar, and a scrolling column of
 * cards. A screen deeper in gets Paytm's back-style header instead of the top bar.
 *
 * Both carry a "Demo data" label. Every figure on every screen is synthetic, and
 * we would rather say so than be asked.
 */

interface Heading {
  title: string;
  sub?: string;
  back: string;
}

function Frame({ children }: { children: React.ReactNode }): React.ReactElement {
  return (
    <div className="paytm-ground mx-auto flex min-h-dvh w-full max-w-[430px] flex-col">
      {children}
    </div>
  );
}

function DemoLabel(): React.ReactElement {
  return (
    <span className="rounded-full bg-white/70 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.06em] text-cyan-text">
      Demo data
    </span>
  );
}

function TopBar({
  avatar,
  business,
}: {
  avatar: React.ReactNode;
  business: boolean;
}): React.ReactElement {
  return (
    <header className="flex items-center gap-2.5 px-3.5 pb-3 pt-3.5">
      <div className="grid size-[30px] flex-none place-items-center rounded-full bg-av-self text-[11.5px] font-extrabold text-av-self-ink [&_svg]:size-4">
        {avatar}
      </div>
      <p className="flex-1 text-[17px] font-extrabold tracking-[-0.04em] text-navy-ink">
        Paytm{" "}
        {business ? (
          <span className="text-[15px] font-bold opacity-90">for Business</span>
        ) : null}
      </p>
      <DemoLabel />
      <Search className="size-[22px] text-navy-ink" />
      {business ? <Bell className="size-[22px] text-navy-ink" /> : null}
    </header>
  );
}

function BackHeader({ title, sub, back }: Heading): React.ReactElement {
  return (
    <header className="flex items-center gap-3 px-3.5 pb-3.5 pt-3">
      <Link href={back} aria-label="Back" className="flex-none text-[20px] leading-none">
        ←
      </Link>
      <div className="min-w-0 flex-1">
        <h1 className="text-[19px] font-extrabold tracking-[-0.025em]">{title}</h1>
        {sub ? <p className="mt-px text-[12px] font-medium text-sub">{sub}</p> : null}
      </div>
      <DemoLabel />
    </header>
  );
}

function Column({ children }: { children: React.ReactNode }): React.ReactElement {
  return <main className="flex flex-1 flex-col gap-[11px] px-2.5 pb-3">{children}</main>;
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w.charAt(0))
    .join("")
    .toUpperCase();
}

/** Paytm for Business, with the shop's initials in the corner. */
export function MerchantShell({
  shopName,
  heading,
  children,
}: {
  shopName?: string;
  heading?: Heading;
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <Frame>
      {heading ? (
        <BackHeader {...heading} />
      ) : (
        <TopBar avatar={initials(shopName ?? "")} business />
      )}
      <Column>{children}</Column>
    </Frame>
  );
}

/** The Paytm app, as the customer sees it. */
export function CustomerShell({
  heading,
  children,
}: {
  heading?: Heading;
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <Frame>
      {heading ? <BackHeader {...heading} /> : <TopBar avatar={<Person />} business={false} />}
      <Column>{children}</Column>
    </Frame>
  );
}
