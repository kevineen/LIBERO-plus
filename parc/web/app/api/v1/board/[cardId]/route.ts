import { NextResponse } from "next/server";

import { deleteBoardCard, updateBoardCard } from "@/lib/board-store";
import type { BoardColumn } from "@/lib/types";

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ cardId: string }> };

/** PATCH /api/v1/board/[cardId] — タイトル / 列 / メモの更新 */
export async function PATCH(request: Request, ctx: Ctx) {
  const { cardId } = await ctx.params;
  const body = (await request.json()) as {
    title?: string;
    notes?: string;
    status?: BoardColumn;
    evalRunId?: string | null;
  };
  const card = updateBoardCard(decodeURIComponent(cardId), body);
  if (!card) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  return NextResponse.json({ card });
}

/** DELETE /api/v1/board/[cardId] */
export async function DELETE(_request: Request, ctx: Ctx) {
  const { cardId } = await ctx.params;
  const ok = deleteBoardCard(decodeURIComponent(cardId));
  if (!ok) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  return NextResponse.json({ ok: true });
}
