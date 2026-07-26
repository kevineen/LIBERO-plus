import { NextResponse } from "next/server";

import { jobsAllowed } from "@/lib/config";
import { parseFleetJson, runParcFleet } from "@/lib/parc-fleet";

export const dynamic = "force-dynamic";

type EnqueueBody = {
  host?: string;
  kind?: string;
  configPath?: string;
  sweep?: string;
  evalConfig?: string;
  notes?: string;
  notify?: boolean;
  params?: Record<string, unknown>;
};

function mapKind(kind: string | undefined): string {
  if (kind === "train") return "train_eval";
  if (kind === "eval") return "eval";
  if (kind === "custom") return "prune";
  if (kind === "train_eval" || kind === "prune") return kind;
  return "train_eval";
}

export async function POST(request: Request) {
  if (!jobsAllowed()) {
    return NextResponse.json(
      { error: "Job launch disabled. Set PARC_WEB_ALLOW_JOBS=1" },
      { status: 403 },
    );
  }
  let body: EnqueueBody;
  try {
    body = (await request.json()) as EnqueueBody;
  } catch {
    return NextResponse.json({ error: "invalid JSON" }, { status: 400 });
  }
  const host = body.host?.trim();
  if (!host) {
    return NextResponse.json({ error: "host required" }, { status: 400 });
  }

  const args = ["enqueue", "--host", host, "--kind", mapKind(body.kind)];
  const sweep =
    body.sweep ||
    (typeof body.params?.sweep === "string" ? body.params.sweep : undefined);
  if (sweep) {
    args.push("--sweep", sweep);
  } else if (body.configPath) {
    const cfg = body.configPath.startsWith("configs/")
      ? body.configPath
      : `configs/experiments/${body.configPath}`;
    args.push("--config", cfg);
  } else {
    return NextResponse.json({ error: "configPath or sweep required" }, { status: 400 });
  }
  if (body.evalConfig || body.params?.evalConfig) {
    args.push("--eval-config", String(body.evalConfig ?? body.params?.evalConfig));
  }
  if (body.notes) {
    args.push("--notes", body.notes);
  }
  if (body.notify || body.params?.notify) {
    args.push("--notify");
  }

  const proc = runParcFleet(args);
  if (!proc.ok) {
    return NextResponse.json(
      { error: proc.stderr || proc.stdout || "parc-fleet enqueue failed" },
      { status: 500 },
    );
  }
  try {
    const data = parseFleetJson(proc.stdout);
    return NextResponse.json({ result: data }, { status: 201 });
  } catch (e) {
    return NextResponse.json(
      {
        error: e instanceof Error ? e.message : String(e),
        raw: proc.stdout.slice(0, 800),
      },
      { status: 500 },
    );
  }
}
