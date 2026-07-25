import { NextResponse } from "next/server";

import { getLauncher } from "@/lib/adapters";

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ jobId: string }> };

export async function GET(_request: Request, ctx: Ctx) {
  const { jobId } = await ctx.params;
  const launcher = getLauncher();
  const job = await launcher.getJob(decodeURIComponent(jobId));
  if (!job) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json({ job });
}

export async function DELETE(_request: Request, ctx: Ctx) {
  const { jobId } = await ctx.params;
  const launcher = getLauncher();
  if (!launcher.cancel) {
    return NextResponse.json({ error: "cancel not supported" }, { status: 405 });
  }
  const job = await launcher.cancel(decodeURIComponent(jobId));
  if (!job) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json({ job });
}
