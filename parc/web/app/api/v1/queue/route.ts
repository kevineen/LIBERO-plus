import { NextResponse } from "next/server";

import { jobsAllowed } from "@/lib/config";
import { parseJsonOutput, runParcQueue } from "@/lib/parc-queue";

export const dynamic = "force-dynamic";

/** キュー進捗・スコア・stale 一覧 */
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const limit = searchParams.get("limit") ?? "40";
  const stale = searchParams.get("staleAfterSec") ?? "3600";
  const res = runParcQueue([
    "status",
    "--json",
    "--limit",
    limit,
    "--stale-after-sec",
    stale,
  ]);
  if (!res.ok) {
    return NextResponse.json(
      { error: res.stderr || res.stdout || "parc-queue status failed" },
      { status: 500 },
    );
  }
  try {
    const data = parseJsonOutput(res.stdout);
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e), raw: res.stdout.slice(0, 2000) },
      { status: 500 },
    );
  }
}

/**
 * POST actions:
 *   { "action": "recover-stale", "maxAgeSec"?: number, "mode"?: "requeue"|"fail" }
 *   { "action": "requeue", "jobId": "..." }
 *   { "action": "resume", "runId": "...", "mode"?: "auto"|"eval"|"train" }
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
    jobId?: string;
    runId?: string;
    maxAgeSec?: number;
    mode?: string;
    notes?: string;
  };
  const action = body.action;
  if (!action) {
    return NextResponse.json({ error: "action required" }, { status: 400 });
  }

  let args: string[] = [];
  if (action === "recover-stale") {
    args = [
      "recover-stale",
      "--max-age-sec",
      String(body.maxAgeSec ?? 3600),
      "--action",
      body.mode === "fail" ? "fail" : "requeue",
    ];
  } else if (action === "requeue") {
    if (!body.jobId) {
      return NextResponse.json({ error: "jobId required" }, { status: 400 });
    }
    args = ["requeue", body.jobId];
  } else if (action === "resume") {
    if (!body.runId) {
      return NextResponse.json({ error: "runId required" }, { status: 400 });
    }
    args = ["resume", body.runId, "--mode", body.mode ?? "auto"];
    if (body.notes) args.push("--notes", body.notes);
  } else {
    return NextResponse.json({ error: `unknown action: ${action}` }, { status: 400 });
  }

  const res = runParcQueue(args);
  if (!res.ok) {
    return NextResponse.json(
      { error: res.stderr || res.stdout || "parc-queue failed" },
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
