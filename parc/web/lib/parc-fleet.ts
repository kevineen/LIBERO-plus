/**
 * Python parc-fleet CLI を呼ぶ薄いヘルパー（Web API 用）。
 */
import { spawnSync } from "node:child_process";

import { getParcRoot } from "@/lib/config";
import { parseJsonOutput } from "@/lib/parc-queue";

export function runParcFleet(args: string[]): {
  ok: boolean;
  stdout: string;
  stderr: string;
  status: number | null;
} {
  const proc = spawnSync("uv", ["run", "parc-fleet", ...args], {
    cwd: getParcRoot(),
    encoding: "utf8",
    env: { ...process.env },
    maxBuffer: 16 * 1024 * 1024,
    // SSH 集約は時間がかかることがある
    timeout: 120_000,
  });
  return {
    ok: proc.status === 0,
    stdout: proc.stdout || "",
    stderr: proc.stderr || "",
    status: proc.status,
  };
}

export function parseFleetJson(stdout: string): unknown {
  return parseJsonOutput(stdout);
}
