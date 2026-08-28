import { NextResponse } from "next/server";

import { createBoardCard, listBoardCards } from "@/lib/board-store";
import type { BoardColumn } from "@/lib/types";

export const dynamic = "force-dynamic";

/** GET /api/v1/board — カンバン全カード */
export async function GET() {
  return NextResponse.json({ cards: listBoardCards() });
}

/** POST /api/v1/board — カード追加 */
export async function POST(request: Request) {
  const body = (await request.json()) as {
    title?: string;
    notes?: string;
    status?: BoardColumn;
    evalRunId?: string | null;
  };
  const title = (body.title ?? "").trim();
  if (!title) {
    return NextResponse.json({ error: "title required" }, { status: 400 });
  }
  const card = createBoardCard({
    title,
    notes: body.notes,
    status: body.status,
    evalRunId: body.evalRunId,
  });
  return NextResponse.json({ card }, { status: 201 });
}
