/**
 * 研究カンバンを experiments/board.json に保存する。
 * 単一ユーザーのローカルコンソール想定なので、ファイル1本で十分。
 */
import fs from "node:fs";
import { randomUUID } from "node:crypto";

import { ensureDir, getBoardPath, getExperimentsDir } from "@/lib/config";
import type { BoardCard, BoardColumn, BoardState } from "@/lib/types";

const COLUMNS: BoardColumn[] = ["todo", "doing", "done"];

function emptyBoard(): BoardState {
  return { cards: [] };
}

function isColumn(v: unknown): v is BoardColumn {
  return v === "todo" || v === "doing" || v === "done";
}

function readBoard(): BoardState {
  const file = getBoardPath();
  try {
    const raw = JSON.parse(fs.readFileSync(file, "utf8")) as Partial<BoardState>;
    const cards = Array.isArray(raw.cards) ? raw.cards : [];
    return {
      cards: cards
        .filter((c) => c && typeof c.id === "string" && typeof c.title === "string")
        .map((c) => ({
          id: c.id,
          title: String(c.title),
          notes: typeof c.notes === "string" ? c.notes : "",
          status: isColumn(c.status) ? c.status : "todo",
          evalRunId: typeof c.evalRunId === "string" && c.evalRunId ? c.evalRunId : null,
          createdAt: typeof c.createdAt === "string" ? c.createdAt : new Date().toISOString(),
          updatedAt: typeof c.updatedAt === "string" ? c.updatedAt : new Date().toISOString(),
        })),
    };
  } catch {
    return emptyBoard();
  }
}

function writeBoard(state: BoardState): void {
  ensureDir(getExperimentsDir());
  const tmp = `${getBoardPath()}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(state, null, 2));
  fs.renameSync(tmp, getBoardPath());
}

export function listBoardCards(): BoardCard[] {
  return readBoard().cards.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
}

export function createBoardCard(input: {
  title: string;
  notes?: string;
  status?: BoardColumn;
  evalRunId?: string | null;
}): BoardCard {
  const now = new Date().toISOString();
  const card: BoardCard = {
    id: randomUUID(),
    title: input.title.trim(),
    notes: (input.notes ?? "").trim(),
    status: input.status && COLUMNS.includes(input.status) ? input.status : "todo",
    evalRunId: input.evalRunId?.trim() || null,
    createdAt: now,
    updatedAt: now,
  };
  const board = readBoard();
  board.cards.push(card);
  writeBoard(board);
  return card;
}

export function updateBoardCard(
  cardId: string,
  patch: Partial<Pick<BoardCard, "title" | "notes" | "status" | "evalRunId">>
): BoardCard | null {
  const board = readBoard();
  const idx = board.cards.findIndex((c) => c.id === cardId);
  if (idx < 0) return null;
  const prev = board.cards[idx];
  const next: BoardCard = {
    ...prev,
    title: patch.title != null ? patch.title.trim() : prev.title,
    notes: patch.notes != null ? patch.notes : prev.notes,
    status: patch.status && COLUMNS.includes(patch.status) ? patch.status : prev.status,
    evalRunId:
      patch.evalRunId === undefined ? prev.evalRunId : patch.evalRunId?.trim() || null,
    updatedAt: new Date().toISOString(),
  };
  board.cards[idx] = next;
  writeBoard(board);
  return next;
}

export function deleteBoardCard(cardId: string): boolean {
  const board = readBoard();
  const next = board.cards.filter((c) => c.id !== cardId);
  if (next.length === board.cards.length) return false;
  writeBoard({ cards: next });
  return true;
}
