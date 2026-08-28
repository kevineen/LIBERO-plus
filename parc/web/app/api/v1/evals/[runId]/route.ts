import { NextResponse } from "next/server";

import { getEvalRun } from "@/lib/eval-logs";

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ runId: string }> };

/** GET /api/v1/evals/[runId] — スイート / タスク / エピソード付き詳細 */
export async function GET(_request: Request, ctx: Ctx) {
  const { runId } = await ctx.params;
  const run = getEvalRun(decodeURIComponent(runId));
  if (!run) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  return NextResponse.json({ run });
}
