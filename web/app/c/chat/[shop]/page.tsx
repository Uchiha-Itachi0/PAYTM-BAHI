import { CustomerThreadScreen } from "@/components/screens/CustomerThreadScreen";

/** C2 · His chat with one shop. */
export default async function Page({
  params,
}: {
  params: Promise<{ shop: string }>;
}): Promise<React.ReactElement> {
  const { shop } = await params;
  return <CustomerThreadScreen shopId={shop} />;
}
