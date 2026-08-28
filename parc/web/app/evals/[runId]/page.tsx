import { EvalDetailView } from "@/components/EvalViews";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ runId: string }> };

export default async function EvalRunPage({ params }: Props) {
  const { runId } = await params;
  return <EvalDetailView runId={decodeURIComponent(runId)} />;
}
