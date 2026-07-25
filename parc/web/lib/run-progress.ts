/**
 * Run 一覧用の学習/評価進捗推定。
 * queue の progress と train_output/checkpoints から組み立てる。
 */
import fs from "node:fs";
import path from "node:path";
import { load as yamlLoad } from "js-yaml";

import { getExperimentsDir } from "@/lib/config";
import type { RunProgress } from "@/lib/types";

type QueueSnap = {
  job_id?: string;
  status?: string;
  run_id?: string | null;
  kind?: string;
  updated_at?: string;
  notes?: string;
};

type ProgressSnap = {
  job_id?: string;
  phase?: string;
  run_id?: string | null;
  step?: number | null;
  total_steps?: number | null;
  percent?: number | null;
  metrics?: { success_rate?: number };
};

function readJson<T>(file: string): T | null {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8")) as T;
  } catch {
    return null;
  }
}

function readYaml(file: string): Record<string, unknown> | null {
  try {
    const doc = yamlLoad(fs.readFileSync(file, "utf8"));
    if (doc && typeof doc === "object") return doc as Record<string, unknown>;
    return null;
  } catch {
    return null;
  }
}

/** queue スナップショットを run_id → 最新ジョブ にマップ */
export function loadQueueByRunId(): Map<string, { job: QueueSnap; progress: ProgressSnap | null }> {
  const map = new Map<string, { job: QueueSnap; progress: ProgressSnap | null; updated: string }>();
  const qdir = path.join(getExperimentsDir(), "queue");
  if (!fs.existsSync(qdir)) return new Map();

  for (const name of fs.readdirSync(qdir)) {
    if (!name.endsWith(".json") || name.includes("progress")) continue;
    if (name === "queue.jsonl") continue;
    const job = readJson<QueueSnap>(path.join(qdir, name));
    if (!job?.job_id) continue;
    const progress = readJson<ProgressSnap>(path.join(qdir, `${job.job_id}.progress.json`));
    const runId = (job.run_id || progress?.run_id || "").trim();
    if (!runId) continue;
    const updated = job.updated_at || "";
    const prev = map.get(runId);
    if (!prev || updated >= prev.updated) {
      map.set(runId, { job, progress, updated });
    }
  }

  const out = new Map<string, { job: QueueSnap; progress: ProgressSnap | null }>();
  for (const [runId, v] of map) {
    out.set(runId, { job: v.job, progress: v.progress });
  }
  return out;
}

function latestCheckpointStep(runDir: string): number | null {
  const roots = [
    path.join(runDir, "train_output", "checkpoints"),
    path.join(runDir, "checkpoints"),
  ];
  let best: number | null = null;
  for (const root of roots) {
    if (!fs.existsSync(root) || !fs.statSync(root).isDirectory()) continue;
    for (const name of fs.readdirSync(root)) {
      const abs = path.join(root, name);
      let st;
      try {
        st = fs.lstatSync(abs);
      } catch {
        continue;
      }
      if (st.isSymbolicLink()) continue;
      if (!st.isDirectory()) continue;
      const n = Number(name);
      if (!Number.isFinite(n)) continue;
      if (best == null || n > best) best = n;
    }
  }
  return best;
}

function trainTotalSteps(runDir: string): number | null {
  const cfg =
    readYaml(path.join(runDir, "config.yaml")) ??
    readYaml(path.join(runDir, "config.source.yaml"));
  const train = cfg?.train;
  if (!train || typeof train !== "object") return null;
  const steps = (train as { steps?: unknown }).steps;
  const updates = (train as { updates?: unknown }).updates;
  if (typeof steps === "number" && steps > 0) return steps;
  if (typeof updates === "number" && updates > 0) return updates;
  return null;
}

/**
 * 単一 run の進捗ビューを作る。
 * queueByRun は listRuns で一度だけ読んで渡す。
 */
export function computeRunProgress(
  runId: string,
  runDir: string,
  status: string,
  queueByRun?: Map<string, { job: QueueSnap; progress: ProgressSnap | null }>
): RunProgress {
  const linked = queueByRun?.get(runId);
  const phase = linked?.progress?.phase || (status === "running" ? "running" : status);
  const jobStatus = linked?.job.status ?? null;
  const jobId = linked?.job.job_id ?? null;

  const totalSteps =
    (typeof linked?.progress?.total_steps === "number" && linked.progress.total_steps > 0
      ? linked.progress.total_steps
      : null) ?? trainTotalSteps(runDir);
  const ckptStep = latestCheckpointStep(runDir);
  const progStep =
    typeof linked?.progress?.step === "number" ? linked.progress.step : null;
  const step =
    ckptStep != null && progStep != null
      ? Math.max(ckptStep, progStep)
      : ckptStep ?? progStep;

  let percent: number | null = null;
  if (typeof linked?.progress?.percent === "number") {
    percent = Math.max(0, Math.min(100, Math.round(linked.progress.percent)));
  } else if (totalSteps && step != null) {
    percent = Math.max(0, Math.min(100, Math.round((100 * step) / totalSteps)));
  } else if (
    (phase === "train" || phase === "running" || status === "running") &&
    totalSteps
  ) {
    // 学習開始直後でもバーを出す（0%）
    percent = 0;
  }

  // フェーズ文言
  let label = "—";
  if (phase === "done" || status === "finished") {
    label = "done";
    if (percent == null) percent = 100;
  } else if (phase === "eval" || phase === "eval_failed") {
    label = phase === "eval_failed" ? "eval failed" : "eval";
    if (percent == null) percent = 95;
  } else if (phase === "train" || phase === "train_done" || phase === "running") {
    if (step != null && totalSteps != null) {
      label = `train ${step}/${totalSteps}`;
    } else if (totalSteps != null && (phase === "train" || status === "running")) {
      label = `train 0/${totalSteps}`;
    } else if (phase === "train_done") {
      label = "train done";
    } else {
      label = "train";
    }
  } else if (phase === "train_failed" || phase === "ckpt_missing") {
    label = String(phase).replaceAll("_", " ");
  } else if (jobStatus === "queued") {
    label = "queued";
  } else if (phase && phase !== status) {
    label = String(phase);
  } else if (status === "running") {
    label = "running";
  }

  return {
    phase: String(phase || status || "unknown"),
    label,
    percent,
    step,
    totalSteps,
    jobId,
    jobStatus,
  };
}
