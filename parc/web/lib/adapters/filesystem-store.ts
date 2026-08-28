import fs from "node:fs";
import path from "node:path";
import { load as yamlLoad } from "js-yaml";

import { getExperimentsDir } from "@/lib/config";
import { computeRunProgress, loadQueueByRunId } from "@/lib/run-progress";
import type {
  Artifact,
  ArtifactKind,
  CategoryStats,
  ExperimentStore,
  RunDetail,
  RunSummary,
} from "@/lib/types";

type RegistryRow = {
  run_id: string;
  name: string;
  created_at: string;
  status: string;
  tags?: string[];
  notes?: string;
  machine_id?: string;
  metrics?: {
    success_rate?: number;
    n_episodes?: number;
    by_category?: Record<string, CategoryStats>;
  };
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

function latestRegistry(): Map<string, RegistryRow> {
  const map = new Map<string, RegistryRow>();
  const reg = path.join(getExperimentsDir(), "registry.jsonl");
  if (!fs.existsSync(reg)) return map;
  const lines = fs.readFileSync(reg, "utf8").split("\n");
  for (const line of lines) {
    if (!line.trim()) continue;
    try {
      const row = JSON.parse(line) as RegistryRow;
      map.set(row.run_id, row);
    } catch {
      /* skip bad line */
    }
  }
  return map;
}

function dirExistsNonEmpty(p: string): boolean {
  try {
    return fs.existsSync(p) && fs.statSync(p).isDirectory() && fs.readdirSync(p).length > 0;
  } catch {
    return false;
  }
}

function guessKind(rel: string): ArtifactKind {
  const lower = rel.toLowerCase();
  if (/\.(mp4|webm|gif)$/.test(lower)) return "video";
  if (/\.(png|jpe?g|webp)$/.test(lower)) return "image";
  if (/\.(json|jsonl|yaml|yml)$/.test(lower)) return "json";
  if (/\.(log|txt)$/.test(lower)) return "log";
  if (lower.includes("checkpoint") || lower.includes("pretrained_model")) return "checkpoint";
  return "other";
}

function walkFiles(root: string, relBase = "", maxDepth = 4, depth = 0): string[] {
  if (depth > maxDepth || !fs.existsSync(root)) return [];
  const out: string[] = [];
  for (const name of fs.readdirSync(root)) {
    if (name === "node_modules" || name.startsWith(".")) continue;
    const abs = path.join(root, name);
    const rel = relBase ? `${relBase}/${name}` : name;
    let st;
    try {
      st = fs.statSync(abs);
    } catch {
      continue;
    }
    if (st.isDirectory()) {
      // checkpoints は深いので先頭だけ
      if (name === "checkpoints" || name === "train_output") {
        out.push(...walkFiles(abs, rel, 2, depth + 1));
      } else {
        out.push(...walkFiles(abs, rel, maxDepth, depth + 1));
      }
    } else {
      out.push(rel);
    }
  }
  return out;
}

function toSummary(
  runId: string,
  row: RegistryRow | undefined,
  runDir: string,
  queueByRun?: ReturnType<typeof loadQueueByRunId>
): RunSummary {
  const meta = readJson<RegistryRow>(path.join(runDir, "meta.json"));
  const metricsFile = readJson<{
    success_rate?: number;
    n_episodes?: number;
  }>(path.join(runDir, "metrics.json"));

  const status = meta?.status ?? row?.status ?? "unknown";
  const tags = meta?.tags ?? row?.tags ?? [];
  const notes = meta?.notes ?? row?.notes ?? "";
  const createdAt = meta?.created_at ?? row?.created_at ?? "";
  const name = meta?.name ?? row?.name ?? runId;
  const machineId = meta?.machine_id ?? row?.machine_id ?? null;

  const successRate =
    metricsFile?.success_rate ??
    meta?.metrics?.success_rate ??
    row?.metrics?.success_rate ??
    null;
  const nEpisodes =
    metricsFile?.n_episodes ??
    meta?.metrics?.n_episodes ??
    row?.metrics?.n_episodes ??
    null;

  return {
    runId,
    name,
    createdAt,
    status,
    tags,
    notes,
    machineId: machineId || null,
    successRate: successRate ?? null,
    nEpisodes: nEpisodes ?? null,
    hasMetrics: fs.existsSync(path.join(runDir, "metrics.json")),
    hasVideos: dirExistsNonEmpty(path.join(runDir, "videos")),
    hasCheckpoints:
      dirExistsNonEmpty(path.join(runDir, "checkpoints")) ||
      dirExistsNonEmpty(path.join(runDir, "train_output")),
    progress: computeRunProgress(runId, runDir, status, queueByRun),
  };
}

/**
 * ローカル experiments/ を読むデフォルトストア。
 * 将来 W&B / DB ストアは同じ ExperimentStore を実装して registry に登録する。
 */
export class FilesystemExperimentStore implements ExperimentStore {
  readonly id = "filesystem";

  async listRuns(opts?: { limit?: number; tag?: string }): Promise<RunSummary[]> {
    const expDir = getExperimentsDir();
    if (!fs.existsSync(expDir)) return [];

    const registry = latestRegistry();
    const queueByRun = loadQueueByRunId();
    const names = fs
      .readdirSync(expDir)
      .filter(
        (n) =>
          n !== "registry.jsonl" &&
          n !== "queue" &&
          n !== "board.json" &&
          fs.statSync(path.join(expDir, n)).isDirectory()
      );

    // registry に無いディレクトリも拾う
    for (const n of names) {
      if (!registry.has(n)) {
        registry.set(n, {
          run_id: n,
          name: n,
          created_at: "",
          status: "unknown",
        });
      }
    }

    let rows = [...registry.values()]
      .filter((r) => fs.existsSync(path.join(expDir, r.run_id)))
      .map((r) => toSummary(r.run_id, r, path.join(expDir, r.run_id), queueByRun))
      .sort((a, b) => b.runId.localeCompare(a.runId));

    if (opts?.tag) {
      rows = rows.filter((r) => r.tags.includes(opts.tag!));
    }
    if (opts?.limit != null) {
      rows = rows.slice(0, opts.limit);
    }
    return rows;
  }

  async getRun(runId: string): Promise<RunDetail | null> {
    const runDir = path.join(getExperimentsDir(), runId);
    if (!fs.existsSync(runDir) || !fs.statSync(runDir).isDirectory()) return null;

    const registry = latestRegistry();
    const summary = toSummary(runId, registry.get(runId), runDir, loadQueueByRunId());
    const metrics = readJson<RunDetail["metrics"]>(path.join(runDir, "metrics.json"));
    const meta = readJson<Record<string, unknown>>(path.join(runDir, "meta.json"));
    const config =
      readYaml(path.join(runDir, "config.yaml")) ??
      readYaml(path.join(runDir, "config.source.yaml"));
    const artifacts = await this.listArtifacts(runId);

    return {
      ...summary,
      config,
      meta,
      metrics,
      artifacts,
      paths: {
        runDir,
        metrics: fs.existsSync(path.join(runDir, "metrics.json"))
          ? path.join(runDir, "metrics.json")
          : undefined,
        config: fs.existsSync(path.join(runDir, "config.yaml"))
          ? path.join(runDir, "config.yaml")
          : undefined,
        videosDir: path.join(runDir, "videos"),
      },
    };
  }

  async listArtifacts(runId: string): Promise<Artifact[]> {
    const runDir = path.join(getExperimentsDir(), runId);
    if (!fs.existsSync(runDir)) return [];

    const interesting = ["videos", "logs", "metrics.json", "episodes.jsonl", "meta.json", "config.yaml"];
    const rels: string[] = [];
    for (const name of interesting) {
      const abs = path.join(runDir, name);
      if (!fs.existsSync(abs)) continue;
      if (fs.statSync(abs).isDirectory()) {
        rels.push(...walkFiles(abs, name, 3));
      } else {
        rels.push(name);
      }
    }
    // train_output の pretrained_model ポインタ程度
    const trainOut = path.join(runDir, "train_output");
    if (fs.existsSync(trainOut)) {
      rels.push(
        ...walkFiles(trainOut, "train_output", 3).filter((r) =>
          /config\.json|metrics|train_config|pretrained_model\/config/.test(r)
        )
      );
    }

    return rels.map((relativePath) => {
      const abs = path.join(runDir, relativePath);
      let bytes: number | null = null;
      try {
        bytes = fs.statSync(abs).size;
      } catch {
        bytes = null;
      }
      const kind = guessKind(relativePath);
      return {
        id: relativePath,
        kind,
        relativePath,
        label: relativePath,
        bytes,
        url: `/api/v1/runs/${encodeURIComponent(runId)}/artifacts/${relativePath
          .split("/")
          .map(encodeURIComponent)
          .join("/")}`,
      };
    });
  }

  async resolveArtifactFile(runId: string, relativePath: string): Promise<string | null> {
    // path traversal 防止
    const normalized = path.normalize(relativePath).replace(/^(\.\.(\/|\\|$))+/, "");
    if (normalized.includes("..")) return null;
    const runDir = path.join(getExperimentsDir(), runId);
    const abs = path.join(runDir, normalized);
    const resolved = path.resolve(abs);
    if (!resolved.startsWith(path.resolve(runDir) + path.sep) && resolved !== path.resolve(runDir)) {
      return null;
    }
    if (!fs.existsSync(resolved) || !fs.statSync(resolved).isFile()) return null;
    return resolved;
  }
}
