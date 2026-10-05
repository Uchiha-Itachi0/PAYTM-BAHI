import { CustomerShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Pill } from "@/components/ui/Pill";
import { LINKS } from "@/lib/config";

/** Where the demo starts: pick a side, or read about the project. */
export default function Start(): React.ReactElement {
  const links = LINKS.filter((l) => l.url);
  return (
    <CustomerShell>
      <Card title="BAHI · the udhaar book both sides can see">
        <p className="mb-4 text-[12.5px] font-medium leading-normal text-sub">
          Two screens that would live inside Paytm: the shopkeeper&apos;s book in Paytm
          for Business, and the customer&apos;s side in the Paytm app. All data is
          synthetic.
        </p>
        <div className="flex flex-col gap-2.5">
          <Pill href="/m">Shopkeeper · Paytm for Business</Pill>
          <Pill href="/c" tone="outline">
            Customer · Paytm app
          </Pill>
        </div>
      </Card>
      {links.length ? (
        <Card title="About the project">
          <p className="mb-3 text-[12.5px] font-medium leading-normal text-sub">
            Selected in the top 10 at the Paytm Build for India AI Hackathon, Mumbai.
            Built by Team Hustlers.
          </p>
          <ul className="flex flex-col">
            {links.map((l) => (
              <li key={l.label} className="border-t border-line first:border-t-0">
                <a
                  href={l.url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center justify-between gap-3 py-2.5"
                >
                  <span className="min-w-0">
                    <span className="block text-[14px] font-extrabold tracking-[-0.02em]">
                      {l.label}
                    </span>
                    <span className="block truncate text-[12px] font-medium text-sub">
                      {l.note}
                    </span>
                  </span>
                  <span aria-hidden className="text-[18px] font-bold text-sub">
                    ↗
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
    </CustomerShell>
  );
}
