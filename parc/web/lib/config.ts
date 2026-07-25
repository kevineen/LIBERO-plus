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

export function jobsAllowed(): boolean {
  return process.env.PARC_WEB_ALLOW_JOBS === "1";
}

export function ensureDir(dir: string): void {
  fs.mkdirSync(dir, { recursive: true });
}

export const WEB_VERSION = "0.1.0";
