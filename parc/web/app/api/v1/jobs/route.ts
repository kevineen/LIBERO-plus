import { NextResponse } from "next/server";

import { getLauncher } from "@/lib/adapters";
import type { JobRequest } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const limit = Number(searchParams.get("limit") ?? "30");
  const launcher = getLauncher();
  const jobs = await launcher.listJobs(Number.isFinite(limit) ? limit : 30);
  return NextResponse.json({ jobs, launcher: launcher.id });
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as JobRequest;
    if (!body?.kind) {
      return NextResponse.json({ error: "kind required" }, { status: 400 });
    }
    const launcher = getLauncher();
    const job = await launcher.launch(body);
    return NextResponse.json({ job }, { status: 201 });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    const status = message.includes("disabled") ? 403 : 400;
    return NextResponse.json({ error: message }, { status });
  }
}
