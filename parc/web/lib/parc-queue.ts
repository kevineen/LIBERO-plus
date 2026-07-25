/**
 * Python キュー CLI を呼ぶ薄いヘルパー（Web API 用）。
 */
import { spawnSync } from "node:child_process";

import { getParcRoot } from "@/lib/config";

export function runParcQueue(args: string[]): {
  ok: boolean;
  stdout: string;
  stderr: string;
  status: number | null;
} {
  const proc = spawnSync("uv", ["run", "parc-queue", ...args], {
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

export function parseJsonOutput(stdout: string): unknown {
  const lines = stdout
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i];
    if (line.startsWith("{") || line.startsWith("[")) {
      try {
        return JSON.parse(line);
      } catch {
        /* continue */
      }
    }
  }
  // 複数行 JSON
  const joined = stdout.trim();
  const start = joined.indexOf("{");
  if (start >= 0) {
    try {
      return JSON.parse(joined.slice(start));
    } catch {
      /* fallthrough */
    }
  }
  throw new Error(`failed to parse parc-queue JSON: ${stdout.slice(0, 500)}`);
}
