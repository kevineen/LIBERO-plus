/**
 * PARC Web — 共有型定義。
 * 新しいストア / ランチャー / ビューアを足すときもこの契約に合わせる。
 */

export type RunStatus = "created" | "running" | "finished" | "failed" | string;

export type CategoryStats = {
  n: number;
  success_rate: number;
  mean_steps?: number;
};

export type RunSummary = {
  runId: string;
  name: string;
  createdAt: string;
  status: RunStatus;
  tags: string[];
  notes: string;
  /** 実行ホスト識別（PARC_MACHINE_ID）。旧 run では null */
  machineId: string | null;
  successRate: number | null;
  nEpisodes: number | null;
  hasMetrics: boolean;
  hasVideos: boolean;
  hasCheckpoints: boolean;
  /** 学習/評価の進行状況（Runs 一覧用） */
  progress?: RunProgress | null;
};

export type RunProgress = {
  phase: string;
  label: string;
  percent: number | null;
  step?: number | null;
  totalSteps?: number | null;
  jobId?: string | null;
  jobStatus?: string | null;
};

export type RunDetail = RunSummary & {
  config: Record<string, unknown> | null;
  meta: Record<string, unknown> | null;
  metrics: {
    success_rate?: number;
    n_episodes?: number;
    by_category?: Record<string, CategoryStats>;
    episodes?: unknown[];
    [key: string]: unknown;
  } | null;
  artifacts: Artifact[];
  paths: {
    runDir: string;
    metrics?: string;
    config?: string;
    videosDir?: string;
  };
};

export type ArtifactKind = "video" | "image" | "json" | "log" | "checkpoint" | "other";

export type Artifact = {
  id: string;
  kind: ArtifactKind;
  relativePath: string;
  label: string;
  bytes: number | null;
  /** API 経由の配信 URL（ブラウザ向け） */
  url: string;
};

export type JobKind = "eval" | "train" | "jupyter" | "custom";

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export type JobRequest = {
  kind: JobKind;
  /** configs/experiments 配下の相対パス、または絶対パス（allowlist 内） */
  configPath?: string;
  notes?: string;
  /** 拡張用の自由パラメータ */
  params?: Record<string, unknown>;
};

export type JobHandle = {
  jobId: string;
  kind: JobKind;
  status: JobStatus;
  createdAt: string;
  updatedAt: string;
  pid: number | null;
  command: string[];
  logPath: string | null;
  runId: string | null;
  error: string | null;
  meta?: Record<string, unknown>;
};

export type HealthResponse = {
  ok: boolean;
  version: string;
  parcRoot: string;
  experimentsDir: string;
  adapters: {
    store: string;
    launcher: string;
  };
  jobsAllowed: boolean;
};

/** 実験ストア（FS / 将来の DB・W&B など） */
export interface ExperimentStore {
  readonly id: string;
  listRuns(opts?: { limit?: number; tag?: string }): Promise<RunSummary[]>;
  getRun(runId: string): Promise<RunDetail | null>;
  listArtifacts(runId: string): Promise<Artifact[]>;
  resolveArtifactFile(runId: string, relativePath: string): Promise<string | null>;
}

/** ジョブランチャー（shell / 将来の queue・k8s など） */
export interface JobLauncher {
  readonly id: string;
  readonly capabilities: JobKind[];
  launch(req: JobRequest): Promise<JobHandle>;
  getJob(jobId: string): Promise<JobHandle | null>;
  listJobs(limit?: number): Promise<JobHandle[]>;
  cancel?(jobId: string): Promise<JobHandle | null>;
}
