/**
 * ジョブを Python 側 queue.jsonl に投入するランチャー。
 * 実際の実行は `parc-worker` が担う（即 spawn しない）。
 */
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";

import {
  ensureDir,
  getConfigsDir,
  getExperimentsDir,
  getParcRoot,
  jobsAllowed,
} from "@/lib/config";
import type { JobHandle, JobKind, JobLauncher, JobRequest, JobStatus } from "@/lib/types";

function nowIso(): string {
  return new Date().toISOString();
}

function queueDir(): string {
  return path.join(getExperimentsDir(), "queue");
}

function jobSnapshotPath(jobId: string): string {
  return path.join(queueDir(), `${jobId}.json`);
}

function resolveConfigPath(configPath: string): string | null {
  const configsDir = path.resolve(getConfigsDir());
  const sweepsDir = path.resolve(path.join(getParcRoot(), "configs", "sweeps"));
  const parcRoot = path.resolve(getParcRoot());
  const raw = path.isAbsolute(configPath)
    ? configPath
    : path.join(
        parcRoot,
        configPath.startsWith("configs/")
          ? configPath
          : path.join("configs/experiments", configPath),
      );
  const resolved = path.resolve(raw);
  const allowed =
    resolved.startsWith(configsDir + path.sep) ||
    resolved.startsWith(sweepsDir + path.sep) ||
    resolved === configsDir ||
    resolved === sweepsDir;
  if (!allowed) return null;
  if (!fs.existsSync(resolved) || !fs.statSync(resolved).isFile()) return null;
  return resolved;
}

function mapKind(kind: JobKind): string {
  if (kind === "train") return "train_eval";
  if (kind === "eval") return "eval";
  if (kind === "custom") return "prune";
  return "train_eval";
}

function readSnapshot(jobId: string): JobHandle | null {
  try {
    const raw = JSON.parse(fs.readFileSync(jobSnapshotPath(jobId), "utf8")) as Record<
      string,
      unknown
    >;
    const statusMap: Record<string, JobStatus> = {
      queued: "queued",
      running: "running",
      done: "succeeded",
      failed: "failed",
      cancelled: "cancelled",
    };
    const st = String(raw.status ?? "queued");
    return {
      jobId: String(raw.job_id ?? jobId),
      kind: (raw.kind as JobKind) ?? "train",
      status: statusMap[st] ?? "queued",
      createdAt: String(raw.created_at ?? nowIso()),
      updatedAt: String(raw.updated_at ?? nowIso()),
      pid: null,
      command: ["parc-enqueue", String(raw.kind ?? "")],
      logPath: path.join(queueDir(), `${jobId}.log`),
      runId: (raw.run_id as string | null) ?? null,
      error: (raw.error as string | null) ?? null,
      meta: raw,
    };
  } catch {
    return null;
  }
}

/**
 * PARC_WEB_LAUNCHER=queue のとき使用。
 * `uv run parc-enqueue` で Python キューへ書き込み、worker が消化する。
 */
export class QueueJobLauncher implements JobLauncher {
  readonly id = "queue";
  readonly capabilities: JobKind[] = ["eval", "train", "custom"];

  async launch(req: JobRequest): Promise<JobHandle> {
    if (!jobsAllowed()) {
      throw new Error("Job launch disabled. Set PARC_WEB_ALLOW_JOBS=1 to enable.");
    }
    if (!this.capabilities.includes(req.kind)) {
      throw new Error(`capability not supported: ${req.kind}`);
    }

    ensureDir(queueDir());
    const parc = getParcRoot();
    const args = ["run", "parc-enqueue", "--kind", mapKind(req.kind)];

    if (req.kind === "custom" && req.params?.sweep) {
      args.push("--sweep", String(req.params.sweep));
    } else if (req.configPath) {
      const abs = resolveConfigPath(req.configPath);
      if (!abs) throw new Error(`config not allowed or missing: ${req.configPath}`);
      args.push("--config", abs);
    } else if (req.params?.sweep) {
      args.push("--sweep", String(req.params.sweep));
    } else {
      throw new Error("configPath or params.sweep required");
    }

    if (req.notes) {
      args.push("--notes", req.notes);
    }
    if (req.params?.evalConfig) {
      args.push("--eval-config", String(req.params.evalConfig));
    }

    const proc = spawnSync("uv", args, {
      cwd: parc,
      encoding: "utf8",
      env: { ...process.env },
    });
    if (proc.status !== 0) {
      throw new Error(
        `parc-enqueue failed: ${(proc.stderr || proc.stdout || "").slice(0, 2000)}`,
      );
    }
    const out = (proc.stdout || "").trim();
    let jobId = `q_${randomUUID().slice(0, 8)}`;
    try {
      // 単発は JSON、スイープはテキスト
      const jsonLine = out
        .split("\n")
        .map((l) => l.trim())
        .filter((l) => l.startsWith("{"))
        .pop();
      if (jsonLine) {
        const parsed = JSON.parse(jsonLine) as { job_id?: string };
        if (parsed.job_id) jobId = parsed.job_id;
      } else {
        const m = out.match(/q_[\w-]+/);
        if (m) jobId = m[0];
      }
    } catch {
      /* keep generated id */
    }

    const snap = readSnapshot(jobId);
    if (snap) return snap;

    return {
      jobId,
      kind: req.kind,
      status: "queued",
      createdAt: nowIso(),
      updatedAt: nowIso(),
      pid: null,
      command: ["uv", ...args],
      logPath: path.join(queueDir(), `${jobId}.log`),
      runId: null,
      error: null,
      meta: { enqueueStdout: out.slice(0, 2000) },
    };
  }

  async getJob(jobId: string): Promise<JobHandle | null> {
    return readSnapshot(jobId);
  }

  async listJobs(limit = 50): Promise<JobHandle[]> {
    ensureDir(queueDir());
    const files = fs
      .readdirSync(queueDir())
      .filter((f) => f.endsWith(".json") && f.startsWith("q_"))
      .sort()
      .reverse()
      .slice(0, limit);
    const jobs: JobHandle[] = [];
    for (const f of files) {
      const job = await this.getJob(f.replace(/\.json$/, ""));
      if (job) jobs.push(job);
    }
    return jobs;
  }

  async cancel(jobId: string): Promise<JobHandle | null> {
    const job = readSnapshot(jobId);
    if (!job) return null;
    // スナップショットを cancelled に書き換え（worker は running のみ実行）
    const rawPath = jobSnapshotPath(jobId);
    try {
      const raw = JSON.parse(fs.readFileSync(rawPath, "utf8")) as Record<string, unknown>;
      if (raw.status === "queued") {
        raw.status = "cancelled";
        raw.updated_at = nowIso();
        fs.writeFileSync(rawPath, JSON.stringify(raw, null, 2));
        // queue.jsonl にも追記（Python update と同等の最低限）
        const qpath = path.join(queueDir(), "queue.jsonl");
        fs.appendFileSync(qpath, JSON.stringify(raw) + "\n");
      }
    } catch {
      /* ignore */
    }
    return readSnapshot(jobId);
  }
}
