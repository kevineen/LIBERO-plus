/**
 * アダプタ登録。新ストア / ランチャーはここに追加する。
 *
 * 例:
 *   registerStore(new WandbExperimentStore(...))
 *   registerLauncher(new QueueJobLauncher(...))
 */
import { FilesystemExperimentStore } from "@/lib/adapters/filesystem-store";
import { QueueJobLauncher } from "@/lib/adapters/queue-launcher";
import { ShellJobLauncher } from "@/lib/adapters/shell-launcher";
import type { ExperimentStore, JobLauncher } from "@/lib/types";

const stores = new Map<string, ExperimentStore>();
const launchers = new Map<string, JobLauncher>();

export function registerStore(store: ExperimentStore): void {
  stores.set(store.id, store);
}

export function registerLauncher(launcher: JobLauncher): void {
  launchers.set(launcher.id, launcher);
}

export function getStore(id?: string): ExperimentStore {
  const key = id ?? process.env.PARC_WEB_STORE ?? "filesystem";
  const store = stores.get(key);
  if (!store) throw new Error(`Unknown experiment store: ${key}`);
  return store;
}

export function getLauncher(id?: string): JobLauncher {
  const key = id ?? process.env.PARC_WEB_LAUNCHER ?? "shell";
  const launcher = launchers.get(key);
  if (!launcher) throw new Error(`Unknown job launcher: ${key}`);
  return launcher;
}

// デフォルト登録
registerStore(new FilesystemExperimentStore());
registerLauncher(new ShellJobLauncher());
registerLauncher(new QueueJobLauncher());
