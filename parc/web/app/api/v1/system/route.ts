import fs from "node:fs";
import path from "node:path";

import { NextResponse } from "next/server";

import { getConfigsDir, getParcRoot, jobsAllowed } from "@/lib/config";
import { getLauncher, getStore } from "@/lib/adapters";

export const dynamic = "force-dynamic";

/** システム情報・利用可能な実験 YAML 一覧（ジョブ UI 用） */
export async function GET() {
  const configsDir = getConfigsDir();
  let configs: string[] = [];
  if (fs.existsSync(configsDir)) {
    configs = fs
      .readdirSync(configsDir)
      .filter((f) => f.endsWith(".yaml") || f.endsWith(".yml"))
      .sort();
  }
  const sweepsDir = path.join(getParcRoot(), "configs", "sweeps");
  let sweeps: string[] = [];
  if (fs.existsSync(sweepsDir)) {
    sweeps = fs
      .readdirSync(sweepsDir)
      .filter((f) => f.endsWith(".yaml") || f.endsWith(".yml"))
      .sort();
  }
  return NextResponse.json({
    parcRoot: getParcRoot(),
    configsDir,
    configs,
    sweeps,
    jobsAllowed: jobsAllowed(),
    store: getStore().id,
    launcher: getLauncher().id,
    capabilities: getLauncher().capabilities,
    docsUrl: "/docs",
    opsManual: "/docs/10_ops_ui",
  });
}
