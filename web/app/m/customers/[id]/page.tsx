import { CustomerScreen } from "@/components/screens/CustomerScreen";

/** One customer: on BAHI or by name, what they owe, and adding their phone. */
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<React.ReactElement> {
  const { id } = await params;
  return <CustomerScreen customerId={id} />;
}
