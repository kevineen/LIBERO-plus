/**
 * lerobot eval_logs を走査し、eval_info.json と videos/ から EvalRun を組み立てる。
 * パッチ前に開始した実行中 eval は、動画フォルダだけで進捗を復元する。
 */
import fs from "node:fs";
import path from "node:path";

import { getEvalLogsDir } from "@/lib/config";
import type {
  EvalEpisode,
  EvalGroupStats,
  EvalRunDetail,
  EvalRunStatus,
  EvalRunSummary,
  EvalTask,
} from "@/lib/types";

type RawTask = {
  task_group?: string;
  task_id?: number;
  metrics?: {
    successes?: boolean[];
    video_paths?: string[];
    sum_rewards?: number[];
  };
};

type RawEvalInfo = {
  status?: string;
  completed_tasks?: number;
  total_tasks?: number;
  per_task?: RawTask[];
  per_group?: Record<
    string,
    { pc_success?: number; n_episodes?: number; video_paths?: string[] }
  >;
  overall?: {
    pc_success?: number;
    n_episodes?: number;
    eval_s?: number;
  };
};

const TASK_DIR_RE = /^(.+)_(\d+)$/;
const EPISODE_RE = /^eval_episode_(\d+)\.mp4$/i;

function readJson<T>(file: string): T | null {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8")) as T;
  } catch {
    return null;
  }
}

function isoFromMtime(file: string): string {
  try {
    return fs.statSync(file).mtime.toISOString();
  } catch {
    return new Date(0).toISOString();
  }
}

function dirExistsNonEmpty(p: string): boolean {
  try {
    return fs.existsSync(p) && fs.statSync(p).isDirectory() && fs.readdirSync(p).length > 0;
  } catch {
    return false;
  }
}

/** runId は eval_logs 直下のディレクトリ名のみ（パストラバーサル禁止）。 */
export function resolveEvalRunDir(runId: string): string | null {
  if (!runId || runId.includes("..") || runId.includes("/") || runId.includes("\\")) {
    return null;
  }
  const root = path.resolve(getEvalLogsDir());
  const abs = path.resolve(path.join(root, runId));
  if (abs !== root && !abs.startsWith(root + path.sep)) return null;
  if (!fs.existsSync(abs) || !fs.statSync(abs).isDirectory()) return null;
  return abs;
}

/** videos/ 配下の相対パスを絶対パスに解決する。 */
export function resolveEvalVideoFile(runId: string, relativePath: string): string | null {
  const runDir = resolveEvalRunDir(runId);
  if (!runDir) return null;
  const videosDir = path.resolve(path.join(runDir, "videos"));
  const normalized = path.normalize(relativePath).replace(/^(\.\.(\/|\\|$))+/, "");
  if (normalized.includes("..")) return null;
  const abs = path.resolve(path.join(videosDir, normalized));
  if (abs !== videosDir && !abs.startsWith(videosDir + path.sep)) return null;
  if (!fs.existsSync(abs) || !fs.statSync(abs).isFile()) return null;
  return abs;
}

function videoUrl(runId: string, rel: string): string {
  return `/api/v1/evals/${encodeURIComponent(runId)}/videos/${rel
    .split("/")
    .map(encodeURIComponent)
    .join("/")}`;
}

function parseTaskDir(name: string): { taskGroup: string; taskId: number } | null {
  const m = name.match(TASK_DIR_RE);
  if (!m) return null;
  return { taskGroup: m[1], taskId: Number(m[2]) };
}

function taskKeyOf(taskGroup: string, taskId: number): string {
  return `${taskGroup}_${taskId}`;
}

/** eval_info に残ったパスから videos/ 以降の相対パスを取り出す。 */
function relFromLoggedVideo(logged: string): string | null {
  const normalized = logged.replaceAll("\\", "/");
  const marker = "/videos/";
  const idx = normalized.indexOf(marker);
  if (idx >= 0) return normalized.slice(idx + marker.length);
  if (normalized.startsWith("videos/")) return normalized.slice("videos/".length);
  if (normalized.includes("/") && !normalized.startsWith("eval_logs/")) {
    return normalized.replace(/^\/+/, "");
  }
  return null;
}

type DiskTask = {
  taskGroup: string;
  taskId: number;
  files: { index: number; rel: string }[];
};

/** videos/{suite}_{id}/eval_episode_N.mp4 をスキャンする。 */
function scanVideoTasks(runDir: string): DiskTask[] {
  const videosDir = path.join(runDir, "videos");
  if (!fs.existsSync(videosDir) || !fs.statSync(videosDir).isDirectory()) return [];
  const out: DiskTask[] = [];
  for (const name of fs.readdirSync(videosDir)) {
    const parsed = parseTaskDir(name);
    if (!parsed) continue;
    const dir = path.join(videosDir, name);
    if (!fs.statSync(dir).isDirectory()) continue;
    const files: { index: number; rel: string }[] = [];
    for (const fname of fs.readdirSync(dir)) {
      const ep = fname.match(EPISODE_RE);
      if (!ep) continue;
      files.push({ index: Number(ep[1]), rel: `${name}/${fname}` });
    }
    files.sort((a, b) => a.index - b.index);
    out.push({ taskGroup: parsed.taskGroup, taskId: parsed.taskId, files });
  }
  out.sort((a, b) => a.taskGroup.localeCompare(b.taskGroup) || a.taskId - b.taskId);
  return out;
}

function inferStatus(runDir: string, info: RawEvalInfo | null): EvalRunStatus {
  if (info?.status === "running" || info?.status === "finished") return info.status;
  // パッチ前の完了ダンプは status が無い
  if (info) return "finished";
  if (dirExistsNonEmpty(path.join(runDir, "videos"))) return "running";
  return "unknown";
}

function rateFromSuccesses(successes: Array<boolean | null>): number | null {
  const known = successes.filter((s): s is boolean => s !== null);
  if (known.length === 0) return null;
  return known.filter(Boolean).length / known.length;
}

function mergeTasks(runId: string, runDir: string, info: RawEvalInfo | null): EvalTask[] {
  const byKey = new Map<string, EvalTask>();
  const disk = scanVideoTasks(runDir);

  for (const d of disk) {
    const key = taskKeyOf(d.taskGroup, d.taskId);
    byKey.set(key, {
      taskKey: key,
      taskGroup: d.taskGroup,
      taskId: d.taskId,
      nEpisodes: d.files.length,
      nSuccess: 0,
      successRate: null,
      episodes: d.files.map((f) => ({
        index: f.index,
        success: null,
        videoUrl: videoUrl(runId, f.rel),
        relativePath: f.rel,
      })),
    });
  }

  for (const raw of info?.per_task ?? []) {
    const taskGroup = String(raw.task_group ?? "unknown");
    const taskId = Number(raw.task_id ?? 0);
    const key = taskKeyOf(taskGroup, taskId);
    const successes = raw.metrics?.successes ?? [];
    const loggedVideos = raw.metrics?.video_paths ?? [];
    const existing = byKey.get(key);
    const n = Math.max(successes.length, loggedVideos.length, existing?.episodes.length ?? 0);
    const episodes: EvalEpisode[] = [];
    for (let i = 0; i < n; i += 1) {
      const fromDisk = existing?.episodes.find((e) => e.index === i);
      const loggedRel = loggedVideos[i] ? relFromLoggedVideo(loggedVideos[i]) : null;
      const rel = fromDisk?.relativePath ?? loggedRel;
      const abs = rel ? path.join(runDir, "videos", rel) : null;
      const hasFile = abs != null && fs.existsSync(abs);
      episodes.push({
        index: i,
        success: typeof successes[i] === "boolean" ? successes[i] : (fromDisk?.success ?? null),
        videoUrl: hasFile && rel ? videoUrl(runId, rel) : (fromDisk?.videoUrl ?? null),
        relativePath: hasFile && rel ? rel : (fromDisk?.relativePath ?? null),
      });
    }
    const nSuccess = episodes.filter((e) => e.success === true).length;
    byKey.set(key, {
      taskKey: key,
      taskGroup,
      taskId,
      nEpisodes: episodes.length,
      nSuccess,
      successRate: rateFromSuccesses(episodes.map((e) => e.success)),
      episodes,
    });
  }

  return [...byKey.values()].sort(
    (a, b) => a.taskGroup.localeCompare(b.taskGroup) || a.taskId - b.taskId
  );
}

function groupsFromTasks(
  tasks: EvalTask[],
  info: RawEvalInfo | null
): EvalGroupStats[] {
  const fromInfo = info?.per_group;
  if (fromInfo && Object.keys(fromInfo).length > 0) {
    return Object.entries(fromInfo)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([taskGroup, g]) => ({
        taskGroup,
        nEpisodes: Number(g.n_episodes ?? 0),
        successRate:
          typeof g.pc_success === "number" && Number.isFinite(g.pc_success)
            ? g.pc_success / 100
            : null,
        nTasks: tasks.filter((t) => t.taskGroup === taskGroup).length,
      }));
  }
  const names = [...new Set(tasks.map((t) => t.taskGroup))].sort();
  return names.map((taskGroup) => {
    const groupTasks = tasks.filter((t) => t.taskGroup === taskGroup);
    const eps = groupTasks.flatMap((t) => t.episodes);
    return {
      taskGroup,
      nEpisodes: eps.length,
      successRate: rateFromSuccesses(eps.map((e) => e.success)),
      nTasks: groupTasks.length,
    };
  });
}

function toSummary(
  runId: string,
  runDir: string,
  info: RawEvalInfo | null,
  tasks: EvalTask[]
): EvalRunSummary {
  const status = inferStatus(runDir, info);
  const infoPath = path.join(runDir, "eval_info.json");
  const videosDir = path.join(runDir, "videos");
  const updatedAt = fs.existsSync(infoPath)
    ? isoFromMtime(infoPath)
    : dirExistsNonEmpty(videosDir)
      ? isoFromMtime(videosDir)
      : isoFromMtime(runDir);

  const overallN =
    typeof info?.overall?.n_episodes === "number" ? info.overall.n_episodes : null;
  const overallSr =
    typeof info?.overall?.pc_success === "number" && Number.isFinite(info.overall.pc_success)
      ? info.overall.pc_success / 100
      : rateFromSuccesses(tasks.flatMap((t) => t.episodes.map((e) => e.success)));

  const completedTasks =
    typeof info?.completed_tasks === "number" ? info.completed_tasks : tasks.length;
  const totalTasks =
    typeof info?.total_tasks === "number" && info.total_tasks > 0 ? info.total_tasks : null;
  const percent =
    totalTasks != null && totalTasks > 0
      ? Math.max(0, Math.min(100, Math.round((100 * completedTasks) / totalTasks)))
      : status === "finished"
        ? 100
        : null;

  return {
    runId,
    status,
    updatedAt,
    nEpisodes: overallN ?? tasks.reduce((s, t) => s + t.nEpisodes, 0),
    successRate: overallSr,
    completedTasks,
    totalTasks,
    percent,
    hasVideos: dirExistsNonEmpty(videosDir),
  };
}

export function listEvalRuns(): EvalRunSummary[] {
  const root = getEvalLogsDir();
  if (!fs.existsSync(root) || !fs.statSync(root).isDirectory()) return [];
  const runs: EvalRunSummary[] = [];
  for (const name of fs.readdirSync(root)) {
    const runDir = path.join(root, name);
    let st: fs.Stats;
    try {
      st = fs.statSync(runDir);
    } catch {
      continue;
    }
    if (!st.isDirectory()) continue;
    const info = readJson<RawEvalInfo>(path.join(runDir, "eval_info.json"));
    const tasks = mergeTasks(name, runDir, info);
    // 空ディレクトリは出さない
    if (!info && tasks.length === 0 && !dirExistsNonEmpty(path.join(runDir, "videos"))) {
      continue;
    }
    runs.push(toSummary(name, runDir, info, tasks));
  }
  runs.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  return runs;
}

export function getEvalRun(runId: string): EvalRunDetail | null {
  const runDir = resolveEvalRunDir(runId);
  if (!runDir) return null;
  const info = readJson<RawEvalInfo>(path.join(runDir, "eval_info.json"));
  const tasks = mergeTasks(runId, runDir, info);
  const summary = toSummary(runId, runDir, info, tasks);
  const evalS =
    typeof info?.overall?.eval_s === "number" && Number.isFinite(info.overall.eval_s)
      ? info.overall.eval_s
      : null;
  return {
    ...summary,
    evalS,
    groups: groupsFromTasks(tasks, info),
    tasks,
    runDir,
  };
}
