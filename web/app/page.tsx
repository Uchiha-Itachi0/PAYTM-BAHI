import { CustomerShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Pill } from "@/components/ui/Pill";

/** Where the demo starts: pick a side. */
export default function Start(): React.ReactElement {
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
    </CustomerShell>
  );
}
