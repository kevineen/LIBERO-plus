import { NextResponse } from "next/server";

import { getStore } from "@/lib/adapters";

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
