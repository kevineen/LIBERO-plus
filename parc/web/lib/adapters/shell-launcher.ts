import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";

import {
  ensureDir,
  getConfigsDir,
  getJobsDir,
  getParcRoot,
  jobsAllowed,
} from "@/lib/config";
import type { JobHandle, JobKind, JobLauncher, JobRequest, JobStatus } from "@/lib/types";

function nowIso(): string {
  return new Date().toISOString();
}

function jobPath(jobId: string): string {
  return path.join(getJobsDir(), `${jobId}.json`);
}

function writeJob(job: JobHandle): void {
  ensureDir(getJobsDir());
  fs.writeFileSync(jobPath(job.jobId), JSON.stringify(job, null, 2));
}

function readJob(jobId: string): JobHandle | null {
  try {
    return JSON.parse(fs.readFileSync(jobPath(jobId), "utf8")) as JobHandle;
  } catch {
    return null;
  }
}

function resolveConfigPath(configPath: string): string | null {
  const configsDir = path.resolve(getConfigsDir());
  const parcRoot = path.resolve(getParcRoot());
  const raw = path.isAbsolute(configPath)
    ? configPath
    : path.join(parcRoot, configPath.startsWith("configs/") ? configPath : path.join("configs/experiments", configPath));
  const resolved = path.resolve(raw);
  // allowlist: configs/experiments 配下のみ
  if (!resolved.startsWith(configsDir + path.sep) && resolved !== configsDir) {
    return null;
  }
  if (!fs.existsSync(resolved) || !fs.statSync(resolved).isFile()) return null;
  return resolved;
}

function buildCommand(req: JobRequest, configAbs: string | null): { cmd: string[]; cwd: string } {
  const parc = getParcRoot();
  const scripts = path.join(parc, "scripts");

  if (req.kind === "eval") {
    if (!configAbs) throw new Error("eval requires configPath");
    // checkpoint 系は eval_ckpt、それ以外は parc.sh
    const cfgText = fs.readFileSync(configAbs, "utf8");
    const isCkpt = /type:\s*checkpoint|type:\s*lerobot\b/.test(cfgText);
    if (isCkpt) {
      return {
        cmd: ["bash", path.join(scripts, "eval_ckpt.sh"), configAbs],
        cwd: parc,
      };
    }
    return {
      cmd: ["bash", path.join(scripts, "parc.sh"), "eval", "-c", configAbs],
      cwd: parc,
    };
  }

  if (req.kind === "train") {
    if (!configAbs) throw new Error("train requires configPath");
    return {
      cmd: ["bash", path.join(scripts, "train.sh"), configAbs],
      cwd: parc,
    };
  }

  if (req.kind === "jupyter") {
    const port = Number(req.params?.port ?? 8888);
    return {
      cmd: ["bash", path.join(scripts, "start_jupyter_remote.sh"), String(port)],
      cwd: parc,
    };
  }

  if (req.kind === "custom") {
    const script = String(req.params?.script ?? "");
    if (!script || script.includes("..") || path.isAbsolute(script)) {
      throw new Error("custom.params.script must be a relative path under scripts/");
    }
    const abs = path.resolve(path.join(parc, "scripts", script));
    if (!abs.startsWith(path.resolve(path.join(parc, "scripts")) + path.sep)) {
      throw new Error("script outside scripts/");
    }
    return { cmd: ["bash", abs], cwd: parc };
  }

  throw new Error(`unsupported kind: ${req.kind}`);
}

function refreshJobStatus(job: JobHandle): JobHandle {
  if (job.status !== "running" || job.pid == null) return job;
  try {
    process.kill(job.pid, 0);
    return job;
  } catch {
    // プロセス終了。ログ末尾で成否を雑に判定
    let status: JobStatus = "succeeded";
    if (job.logPath && fs.existsSync(job.logPath)) {
      const tail = fs.readFileSync(job.logPath, "utf8").slice(-4000);
      if (/Traceback|ERROR|eval failed|train failed|exit_code=[1-9]/i.test(tail)) {
        status = "failed";
      }
    }
    const updated: JobHandle = {
      ...job,
      status,
      updatedAt: nowIso(),
      pid: null,
    };
    writeJob(updated);
    return updated;
  }
}

/**
 * ローカル shell で train/eval/jupyter を起動するデフォルトランチャー。
 * PARC_WEB_ALLOW_JOBS=1 のときのみ launch 可。
 */
export class ShellJobLauncher implements JobLauncher {
  readonly id = "shell";
  readonly capabilities: JobKind[] = ["eval", "train", "jupyter", "custom"];

  async launch(req: JobRequest): Promise<JobHandle> {
    if (!jobsAllowed()) {
      throw new Error("Job launch disabled. Set PARC_WEB_ALLOW_JOBS=1 to enable.");
    }
    if (!this.capabilities.includes(req.kind)) {
      throw new Error(`capability not supported: ${req.kind}`);
    }

    const configAbs = req.configPath ? resolveConfigPath(req.configPath) : null;
    if (req.configPath && !configAbs) {
      throw new Error(`config not allowed or missing: ${req.configPath}`);
    }

    const { cmd, cwd } = buildCommand(req, configAbs);
    const jobId = `job_${nowIso().replace(/[:.]/g, "")}_${randomUUID().slice(0, 8)}`;
    ensureDir(getJobsDir());
    const logPath = path.join(getJobsDir(), `${jobId}.log`);
    const logFd = fs.openSync(logPath, "a");

    const child = spawn(cmd[0], cmd.slice(1), {
      cwd,
      detached: true,
      stdio: ["ignore", logFd, logFd],
      env: {
        ...process.env,
        MUJOCO_GL: process.env.MUJOCO_GL ?? "egl",
      },
    });
    fs.closeSync(logFd);
    child.unref();

    const job: JobHandle = {
      jobId,
      kind: req.kind,
      status: "running",
      createdAt: nowIso(),
      updatedAt: nowIso(),
      pid: child.pid ?? null,
      command: cmd,
      logPath,
      runId: null,
      error: null,
      meta: {
        configPath: configAbs,
        notes: req.notes ?? "",
        params: req.params ?? {},
      },
    };
    writeJob(job);
    return job;
  }

  async getJob(jobId: string): Promise<JobHandle | null> {
    const job = readJob(jobId);
    if (!job) return null;
    return refreshJobStatus(job);
  }

  async listJobs(limit = 50): Promise<JobHandle[]> {
    ensureDir(getJobsDir());
    const files = fs
      .readdirSync(getJobsDir())
      .filter((f) => f.endsWith(".json"))
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
    const job = readJob(jobId);
    if (!job || job.pid == null) return job;
    try {
      process.kill(-job.pid, "SIGTERM");
    } catch {
      try {
        process.kill(job.pid, "SIGTERM");
      } catch {
        /* already gone */
      }
    }
    const updated: JobHandle = {
      ...job,
      status: "cancelled",
      updatedAt: nowIso(),
      pid: null,
    };
    writeJob(updated);
    return updated;
  }
}
