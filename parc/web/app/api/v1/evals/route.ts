import { NextResponse } from "next/server";

import { getEvalLogsDir } from "@/lib/config";
import { listEvalRuns } from "@/lib/eval-logs";

export const dynamic = "force-dynamic";

/** GET /api/v1/evals — eval_logs 配下の評価実行一覧 */
export async function GET() {
  const runs = listEvalRuns();
  return NextResponse.json({
    runs,
    evalLogsDir: getEvalLogsDir(),
  });
}
