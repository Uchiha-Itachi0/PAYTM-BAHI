import { PayScreen } from "@/components/screens/PayScreen";

/** Paying a shop: the amount, Proceed securely, the UPI PIN. */
export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ shop: string }>;
  searchParams: Promise<{ from?: string }>;
}): Promise<React.ReactElement> {
  const { shop } = await params;
  const { from } = await searchParams;
  return <PayScreen shopId={shop} from={from ?? "chat"} />;
}
