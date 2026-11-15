import { CircleScreen } from "@/components/screens/CircleScreen";

/** C3 · One circle: who is in it, and its list. */
export default async function Page({
  params,
}: {
  params: Promise<{ circle: string }>;
}): Promise<React.ReactElement> {
  const { circle } = await params;
  return <CircleScreen circleId={circle} />;
}
