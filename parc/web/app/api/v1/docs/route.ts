import fs from "node:fs";
import path from "node:path";

import { NextResponse } from "next/server";

import { getParcRoot } from "@/lib/config";

export const dynamic = "force-dynamic";

const DOC_ALLOW = new Set([
  "00_overview",
  "01_setup",
  "02_data",
  "03_train",
  "04_eval",
  "05_experiments",
  "06_competition",
  "07_custom_data_and_algos",
  "08_remote_and_ui",
  "09_autoloop_and_rl",
  "10_ops_ui",
]);

function docsDir(): string {
  return path.join(getParcRoot(), "docs");
}

/** マニュアル一覧 */
export async function GET() {
  const dir = docsDir();
  if (!fs.existsSync(dir)) {
    return NextResponse.json({ docs: [] });
  }
  const files = fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".md"))
    .sort()
    .map((f) => {
      const id = f.replace(/\.md$/, "");
      const text = fs.readFileSync(path.join(dir, f), "utf8");
      const title =
        text
          .split("\n")
          .find((l) => l.startsWith("# "))
          ?.replace(/^#\s+/, "")
          .trim() || id;
      return {
        id,
        file: f,
        title,
        url: `/docs/${encodeURIComponent(id)}`,
        apiUrl: `/api/v1/docs/${encodeURIComponent(id)}`,
      };
    });
  return NextResponse.json({ docs: files, allow: [...DOC_ALLOW] });
}
