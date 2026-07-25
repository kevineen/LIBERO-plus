import { NextResponse } from "next/server";

import { getStore } from "@/lib/adapters";

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ runId: string }> };

export async function GET(_request: Request, ctx: Ctx) {
  const { runId } = await ctx.params;
  const store = getStore();
  const run = await store.getRun(decodeURIComponent(runId));
  if (!run) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  return NextResponse.json({ run, store: store.id });
}
