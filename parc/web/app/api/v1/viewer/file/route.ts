import fs from "node:fs";
import path from "node:path";
import { Readable } from "node:stream";

import { NextResponse } from "next/server";

import { getParcRoot } from "@/lib/config";

export const dynamic = "force-dynamic";

const MIME: Record<string, string> = {
  ".glb": "model/gltf-binary",
  ".bin": "application/octet-stream",
  ".mp4": "video/mp4",
  ".json": "application/json",
};

function packsRoot(): string {
  return path.join(getParcRoot(), "data", "viewer_packs");
}

/** viewer_packs 配下のファイルをストリーム配信（Range 対応・path 突き合わせ）。 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const rel = url.searchParams.get("path") ?? "";
  if (!rel || rel.includes("..") || rel.startsWith("/")) {
    return NextResponse.json({ error: "invalid path" }, { status: 400 });
  }
  const root = packsRoot();
  const abs = path.resolve(root, rel);
  if (!abs.startsWith(root + path.sep)) {
    return NextResponse.json({ error: "invalid path" }, { status: 400 });
  }
  if (!fs.existsSync(abs) || !fs.statSync(abs).isFile()) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }

  const stat = fs.statSync(abs);
  const contentType = MIME[path.extname(abs).toLowerCase()] ?? "application/octet-stream";
  const range = request.headers.get("range");

  const baseHeaders: Record<string, string> = {
    "Content-Type": contentType,
    "Accept-Ranges": "bytes",
    "Cache-Control": "private, max-age=60",
  };

  if (range) {
    const match = /bytes=(\d*)-(\d*)/.exec(range);
    if (match) {
      const start = match[1] ? parseInt(match[1], 10) : 0;
      const end = match[2] ? Math.min(parseInt(match[2], 10), stat.size - 1) : stat.size - 1;
      if (start >= stat.size || start > end) {
        return new NextResponse(null, {
          status: 416,
          headers: { "Content-Range": `bytes */${stat.size}` },
        });
      }
      const stream = fs.createReadStream(abs, { start, end });
      return new NextResponse(Readable.toWeb(stream) as unknown as ReadableStream, {
        status: 206,
        headers: {
          ...baseHeaders,
          "Content-Range": `bytes ${start}-${end}/${stat.size}`,
          "Content-Length": String(end - start + 1),
        },
      });
    }
  }

  const stream = fs.createReadStream(abs);
  return new NextResponse(Readable.toWeb(stream) as unknown as ReadableStream, {
    status: 200,
    headers: { ...baseHeaders, "Content-Length": String(stat.size) },
  });
}
