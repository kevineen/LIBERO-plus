import { EvalSuiteView } from "@/components/EvalViews";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ runId: string; suite: string }> };

export default async function EvalSuitePage({ params }: Props) {
  const { runId, suite } = await params;
  return (
    <EvalSuiteView
      runId={decodeURIComponent(runId)}
      suite={decodeURIComponent(suite)}
    />
  );
}
