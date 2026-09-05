import fs from "node:fs";
import path from "node:path";

import { NextResponse } from "next/server";

import { getParcRoot } from "@/lib/config";

export const dynamic = "force-dynamic";

/** ビューア用 scene pack インデックス（parc-export-viewer が生成）。 */
export async function GET() {
  const indexPath = path.join(getParcRoot(), "data", "viewer_packs", "index.json");
  if (!fs.existsSync(indexPath)) {
    return NextResponse.json(
      {
        format_version: 1,
        generated: null,
        n_episodes: 0,
        episodes: [],
        hint: "parc-export-viewer を実行して scene pack を生成してください",
      },
      { status: 200 },
    );
  }
  const index = JSON.parse(fs.readFileSync(indexPath, "utf8"));
  return NextResponse.json(index);
}
