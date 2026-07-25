import fs from "node:fs";
import path from "node:path";

import { NextResponse } from "next/server";

import { getParcRoot } from "@/lib/config";

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ slug: string }> };

const SAFE = /^[0-9a-zA-Z_-]+$/;

/** マニュアル本文（markdown） */
export async function GET(_request: Request, ctx: Ctx) {
  const { slug } = await ctx.params;
  const id = decodeURIComponent(slug);
  if (!SAFE.test(id)) {
    return NextResponse.json({ error: "invalid slug" }, { status: 400 });
  }
  const file = path.join(getParcRoot(), "docs", `${id}.md`);
  const resolved = path.resolve(file);
  const root = path.resolve(path.join(getParcRoot(), "docs"));
  if (!resolved.startsWith(root + path.sep)) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }
  if (!fs.existsSync(resolved)) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  const markdown = fs.readFileSync(resolved, "utf8");
  return NextResponse.json({
    id,
    title:
      markdown
        .split("\n")
        .find((l) => l.startsWith("# "))
        ?.replace(/^#\s+/, "")
        .trim() || id,
    markdown,
  });
}
