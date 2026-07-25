import fs from "node:fs";
import path from "node:path";

import { NextResponse } from "next/server";

import { getStore } from "@/lib/adapters";

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ runId: string; path: string[] }> };

const MIME: Record<string, string> = {
  ".mp4": "video/mp4",
  ".webm": "video/webm",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".gif": "image/gif",
  ".json": "application/json",
  ".jsonl": "application/x-ndjson",
  ".yaml": "text/yaml",
  ".yml": "text/yaml",
  ".txt": "text/plain",
  ".log": "text/plain",
};

export async function GET(_request: Request, ctx: Ctx) {
  const { runId, path: parts } = await ctx.params;
  const relativePath = parts.map(decodeURIComponent).join("/");
  const store = getStore();
  const abs = await store.resolveArtifactFile(decodeURIComponent(runId), relativePath);
  if (!abs) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  const buf = fs.readFileSync(abs);
  const ext = path.extname(abs).toLowerCase();
  const contentType = MIME[ext] ?? "application/octet-stream";
  return new NextResponse(buf, {
    headers: {
      "Content-Type": contentType,
      "Cache-Control": "private, max-age=60",
    },
  });
}
