import { CirclePayScreen } from "@/components/screens/CirclePayScreen";

/** C5 · Paying a bill on a circle's list. */
export default async function Page({
  params,
}: {
  params: Promise<{ circle: string; entry: string }>;
}): Promise<React.ReactElement> {
  const { circle, entry } = await params;
  return <CirclePayScreen circleId={circle} entryId={entry} />;
}
