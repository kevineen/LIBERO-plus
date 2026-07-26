import { NextResponse } from "next/server";

import { getStore } from "@/lib/adapters";
import { jobsAllowed } from "@/lib/config";
import { parseJsonOutput, runParcList } from "@/lib/parc-list";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const limit = Number(searchParams.get("limit") ?? "50");
  const tag = searchParams.get("tag") ?? undefined;
  const store = getStore();
  const runs = await store.listRuns({
    limit: Number.isFinite(limit) ? limit : 50,
    tag,
  });
  return NextResponse.json({ runs, store: store.id });
}

/**
 * POST actions (local only):
 *   { "action": "delete", "runId"?: "...", "failed"?: true, "paused"?: true }
 * run ディレクトリごと削除（parc-list delete）。
 */
export async function POST(request: Request) {
  if (!jobsAllowed()) {
    return NextResponse.json(
      { error: "Job launch disabled. Set PARC_WEB_ALLOW_JOBS=1" },
      { status: 403 },
    );
  }
  const body = (await request.json()) as {
    action?: string;
    runId?: string;
    failed?: boolean;
    paused?: boolean;
  };
  if (body.action !== "delete") {
    return NextResponse.json({ error: `unknown action: ${body.action}` }, { status: 400 });
  }
  const args = ["delete"];
  if (body.runId) args.push(body.runId);
  if (body.failed) args.push("--failed");
  if (body.paused) args.push("--paused");
  if (!body.runId && !body.failed && !body.paused) {
    return NextResponse.json(
      { error: "runId or failed/paused required" },
      { status: 400 },
    );
  }
  const res = runParcList(args);
  if (!res.ok) {
    return NextResponse.json(
      { error: res.stderr || res.stdout || "parc-list delete failed" },
      { status: 400 },
    );
  }
  try {
    const data = parseJsonOutput(res.stdout);
    return NextResponse.json({ ok: true, result: data });
  } catch {
    return NextResponse.json({ ok: true, raw: res.stdout.trim() });
  }
}
