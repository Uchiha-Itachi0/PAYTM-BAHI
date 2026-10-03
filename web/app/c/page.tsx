import { Bank, Book, Mobile, Scan } from "@/components/icons";
import { CustomerShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { StickyPill } from "@/components/ui/StickyPill";
import { TileGrid } from "@/components/ui/TileGrid";

/**
 * The customer's side: the Paytm app home, with one new tile.
 *
 * Nobody downloads anything. Udhaar sits beside Scan & Pay and To Mobile in the
 * app already on his phone, which is the whole answer to cold start. His own
 * book, the confirmation sheet and the pay action arrive in F5 and F6.
 */
export default function CustomerHome(): React.ReactElement {
  return (
    <CustomerShell>
      <Card title="Money Transfer">
        <TileGrid
          tiles={[
            { label: "Scan & Pay", icon: <Scan /> },
            { label: "To Mobile", icon: <Mobile /> },
            { label: "To Bank", icon: <Bank /> },
            { label: "Udhaar", icon: <Book />, href: "/c" },
          ]}
        />
      </Card>
      <StickyPill icon={<Scan />}>Scan QR</StickyPill>
    </CustomerShell>
  );
}
