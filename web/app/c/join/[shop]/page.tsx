import { JoinScreen } from "@/components/screens/JoinScreen";

/** B0 → B1 · Where the udhaar QR lands. */
export default async function Page({
  params,
}: {
  params: Promise<{ shop: string }>;
}): Promise<React.ReactElement> {
  const { shop } = await params;
  return <JoinScreen shopId={shop} />;
}
