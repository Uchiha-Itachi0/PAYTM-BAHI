import { headers } from "next/headers";
import QRCode from "qrcode";

import { MerchantShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Notice } from "@/components/ui/Notice";
import { SHOP_ID } from "@/lib/config";
import { onlyHere, wifiAddress } from "@/lib/lan";

/**
 * The shop's udhaar QR: a second code beside the pay QR, so a customer who is
 * only paying never sees udhaar.
 *
 * The link is built from the address this page was opened on, so on the
 * deployed site any phone can scan it. Opened on localhost (the laptop, where the
 * mic works), the link uses the laptop's wifi address instead, so a phone on the
 * same wifi can scan it too.
 */
export default async function Page(): Promise<React.ReactElement> {
  const h = await headers();
  const opened = h.get("x-forwarded-host") ?? h.get("host") ?? "localhost:3000";
  const proto = h.get("x-forwarded-proto") ?? "http";
  const wifi = onlyHere(opened) ? wifiAddress() : null;
  const port = opened.match(/:(\d+)$/)?.[1];
  const host = wifi ? `${wifi}${port ? `:${port}` : ""}` : opened;
  const link = `${proto}://${host}/c/join/${SHOP_ID}`;
  const svg = await QRCode.toString(link, { type: "svg", margin: 1, width: 240 });

  return (
    <MerchantShell heading={{ title: "Udhaar QR", sub: "Keep it beside the pay QR", back: "/m" }}>
      <Card>
        <div className="flex flex-col items-center gap-3 py-2">
          <div
            className="size-60 [&_svg]:size-full"
            dangerouslySetInnerHTML={{ __html: svg }}
          />
          <p className="text-[15px] font-extrabold tracking-[-0.02em]">Udhaar? Scan here</p>
          <p className="break-all text-center text-[11px] font-medium text-sub">{link}</p>
        </div>
      </Card>
      <Notice>
        Scanning says only &ldquo;I&apos;m at the counter&rdquo;. It records nothing. Your
        Soundbox chimes, and their name appears on your screen, never out loud.
      </Notice>
      {wifi ? (
        <Notice>
          This QR uses the laptop&apos;s wifi address, so a phone on the same wifi can scan it.
          If it won&apos;t open, the wifi may keep devices apart (many offices do): use a
          phone&apos;s hotspot for both, or the deployed site.
        </Notice>
      ) : onlyHere(opened) ? (
        <Notice tone="warn">
          A phone cannot open localhost, and this laptop isn&apos;t on a wifi a phone could
          reach. Join one, or use the deployed site.
        </Notice>
      ) : null}
    </MerchantShell>
  );
}
