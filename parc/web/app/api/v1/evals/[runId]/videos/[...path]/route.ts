import fs from "node:fs";
import path from "node:path";
import { Readable } from "node:stream";

import { NextResponse } from "next/server";

import { resolveEvalVideoFile } from "@/lib/eval-logs";

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ runId: string; path: string[] }> };

const MIME: Record<string, string> = {
  ".mp4": "video/mp4",
  ".webm": "video/webm",
  ".gif": "image/gif",
};

/**
 * GET /api/v1/evals/[runId]/videos/[...path]
 * Range 対応で mp4 をストリームする（シーク用。全体をメモリに載せない）。
 */
export async function GET(request: Request, ctx: Ctx) {
  const { runId, path: parts } = await ctx.params;
  const relativePath = parts.map(decodeURIComponent).join("/");
  const abs = resolveEvalVideoFile(decodeURIComponent(runId), relativePath);
  if (!abs) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }

  const stat = fs.statSync(abs);
  const ext = path.extname(abs).toLowerCase();
  const contentType = MIME[ext] ?? "application/octet-stream";
  const range = request.headers.get("range");

  const toWeb = (stream: fs.ReadStream) =>
    Readable.toWeb(stream) as unknown as ReadableStream<Uint8Array>;

  if (range) {
    const m = /bytes=(\d+)-(\d*)/.exec(range);
    if (!m) {
      return NextResponse.json({ error: "invalid range" }, { status: 416 });
    }
    const start = Number(m[1]);
    const end = m[2] ? Number(m[2]) : Math.min(start + 1024 * 1024 - 1, stat.size - 1);
    if (start >= stat.size || end >= stat.size || start > end) {
      return new NextResponse(null, {
        status: 416,
        headers: { "Content-Range": `bytes */${stat.size}` },
      });
    }
    const stream = fs.createReadStream(abs, { start, end });
    return new NextResponse(toWeb(stream), {
      status: 206,
      headers: {
        "Content-Type": contentType,
        "Content-Range": `bytes ${start}-${end}/${stat.size}`,
        "Accept-Ranges": "bytes",
        "Content-Length": String(end - start + 1),
        "Cache-Control": "private, max-age=60",
      },
    });
  }

  const stream = fs.createReadStream(abs);
  return new NextResponse(toWeb(stream), {
    headers: {
      "Content-Type": contentType,
      "Content-Length": String(stat.size),
      "Accept-Ranges": "bytes",
      "Cache-Control": "private, max-age=60",
    },
  });
}
