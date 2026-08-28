import { EvalTaskView } from "@/components/EvalViews";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ runId: string; taskKey: string }> };

export default async function EvalTaskPage({ params }: Props) {
  const { runId, taskKey } = await params;
  return (
    <EvalTaskView
      runId={decodeURIComponent(runId)}
      taskKey={decodeURIComponent(taskKey)}
    />
  );
}
