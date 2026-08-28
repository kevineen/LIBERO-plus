import path from "node:path";
import fs from "node:fs";

/** parc/ ルート（web/ の親）。環境変数で上書き可。 */
export function getParcRoot(): string {
  if (process.env.PARC_ROOT) {
    return path.resolve(process.env.PARC_ROOT);
  }
  return path.resolve(process.cwd(), "..");
}

export function getExperimentsDir(): string {
  if (process.env.PARC_EXPERIMENTS_DIR) {
    return path.resolve(process.env.PARC_EXPERIMENTS_DIR);
  }
  return path.join(getParcRoot(), "experiments");
}

export function getJobsDir(): string {
  return path.join(getParcRoot(), "web", ".parc-jobs");
}

export function getConfigsDir(): string {
  return path.join(getParcRoot(), "configs", "experiments");
}

/**
 * lerobot-eval の output_dir 親（eval_logs）。
 * PARC ルートの兄弟 `lerobot/eval_logs` がデフォルト。
 */
export function getEvalLogsDir(): string {
  if (process.env.LEROBOT_EVAL_LOGS_DIR) {
    return path.resolve(process.env.LEROBOT_EVAL_LOGS_DIR);
  }
  return path.resolve(getParcRoot(), "..", "lerobot", "eval_logs");
}

/** 研究カンバンの保存先（experiments 配下の 1 JSON）。 */
export function getBoardPath(): string {
  return path.join(getExperimentsDir(), "board.json");
}

export function jobsAllowed(): boolean {
  return process.env.PARC_WEB_ALLOW_JOBS === "1";
}

export function ensureDir(dir: string): void {
  fs.mkdirSync(dir, { recursive: true });
}

export const WEB_VERSION = "0.1.0";
