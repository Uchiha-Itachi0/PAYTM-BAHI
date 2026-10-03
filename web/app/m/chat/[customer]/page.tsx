import { ShopThreadScreen } from "@/components/screens/ShopThreadScreen";

/** C3 · One customer's thread. */
export default async function Page({
  params,
}: {
  params: Promise<{ customer: string }>;
}): Promise<React.ReactElement> {
  const { customer } = await params;
  return <ShopThreadScreen customerId={customer} />;
}
