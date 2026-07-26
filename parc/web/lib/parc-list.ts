/**
 * Python parc-list CLI を呼ぶ薄いヘルパー（Web API 用）。
 */
import { spawnSync } from "node:child_process";

import { getParcRoot } from "@/lib/config";
import { parseJsonOutput } from "@/lib/parc-queue";

export function runParcList(args: string[]): {
  ok: boolean;
  stdout: string;
  stderr: string;
  status: number | null;
} {
  const proc = spawnSync("uv", ["run", "parc-list", ...args], {
    cwd: getParcRoot(),
    encoding: "utf8",
    env: { ...process.env },
    maxBuffer: 8 * 1024 * 1024,
  });
  return {
    ok: proc.status === 0,
    stdout: proc.stdout || "",
    stderr: proc.stderr || "",
    status: proc.status,
  };
}

export { parseJsonOutput };
