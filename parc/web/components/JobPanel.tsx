"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import type { JobHandle, JobKind } from "@/lib/types";

type QueueJobRow = {
  job_id: string;
  kind: string;
  status: string;
  stale?: boolean;
  host?: string;
  local?: boolean;
  run_id?: string | null;
  error?: string | null;
  progress?: {
    phase?: string;
    step?: number | null;
    total_steps?: number | null;
    percent?: number | null;
    metrics?: { success_rate?: number };
  };
  metrics?: { success_rate?: number; n_episodes?: number } | null;
  rl_latest?: { update?: number; mean_reward?: number; loss?: number } | null;
};

type QueueStatus = {
  counts?: Record<string, number>;
  stale_running?: QueueJobRow[];
  jobs?: QueueJobRow[];
  top_scores?: { run_id?: string; success_rate?: number; job_id?: string }[];
};

type SystemInfo = {
  configs: string[];
  sweeps?: string[];
  jobsAllowed: boolean;
  capabilities: JobKind[];
  launcher?: string;
};

type FleetHost = {
  alias: string;
  kind?: string;
  reachable?: boolean;
  tunnel_hint?: string | null;
};

export function JobPanel() {
  const [jobs, setJobs] = useState<JobHandle[]>([]);
  const [queue, setQueue] = useState<QueueStatus | null>(null);
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [hosts, setHosts] = useState<FleetHost[]>([]);
  const [localAlias, setLocalAlias] = useState("local");
  const [targetHost, setTargetHost] = useState("local");
  const [kind, setKind] = useState<JobKind>("train");
  const [config, setConfig] = useState("");
  const [sweep, setSweep] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [j, s, q, fh] = await Promise.all([
      fetch("/api/v1/jobs?limit=30").then((r) => r.json()),
      fetch("/api/v1/system").then((r) => r.json()),
      fetch("/api/v1/fleet/queue?limit=40")
        .then((r) => r.json())
        .catch(() => null),
      fetch("/api/v1/fleet/hosts")
        .then((r) => r.json())
        .catch(() => null),
    ]);
    setJobs(j.jobs ?? []);
    if (q && !q.error) {
      const jobsRows = (q.jobs ?? []) as QueueJobRow[];
      const counts: Record<string, number> = {};
      for (const block of q.hosts ?? []) {
        for (const [k, v] of Object.entries(block.counts ?? {})) {
          counts[k] = (counts[k] ?? 0) + Number(v);
        }
      }
      setQueue({
        counts,
        jobs: jobsRows,
        stale_running: [],
        top_scores: [],
      });
    } else {
      setQueue(null);
    }
    if (fh && fh.hosts) {
      setHosts(fh.hosts as FleetHost[]);
      if (fh.local_alias) {
        setLocalAlias(String(fh.local_alias));
        setTargetHost((prev) => (prev === "local" ? String(fh.local_alias) : prev));
      }
    }
    setSystem({
      configs: s.configs ?? [],
      sweeps: s.sweeps ?? [],
      jobsAllowed: !!s.jobsAllowed,
      capabilities: s.capabilities ?? [],
      launcher: s.launcher,
    });
    if (!config && (s.configs?.length ?? 0) > 0) {
      setConfig(s.configs[0]);
    }
    if (!sweep && (s.sweeps?.length ?? 0) > 0) {
      setSweep(s.sweeps[0]);
    }
  }, [config, sweep]);

  useEffect(() => {
    void refresh();
    const t = setInterval(() => void refresh(), 8000);
    return () => clearInterval(t);
  }, [refresh]);

  async function launch() {
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const host = targetHost || localAlias;
      const body: Record<string, unknown> = { host, kind };
      if (kind === "custom" && sweep) {
        body.sweep = sweep.startsWith("configs/") ? sweep : `configs/sweeps/${sweep}`;
      } else if (kind === "eval" || kind === "train") {
        body.configPath = config;
      }
      const res = await fetch("/api/v1/fleet/enqueue", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? res.statusText);
      const result = data.result ?? data;
      setMsg(
        `queued on ${result.host ?? host}: ${result.job_id ?? JSON.stringify(result).slice(0, 120)}`,
      );
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function queueAction(payload: Record<string, unknown>) {
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      // ローカルキュー操作のみ（リモート requeue は parc-remote 経由が別途必要）
      const res = await fetch("/api/v1/queue", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? res.statusText);
      setMsg(JSON.stringify(data.result ?? data).slice(0, 240));
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function cancelJob(jobId: string, host?: string) {
    setBusy(true);
    setError(null);
    try {
      if (host && host !== localAlias) {
        setError(`Pause/Cancel on remote: uv run parc-remote ${host} queue cancel ${jobId}`);
        return;
      }
      const res = await fetch("/api/v1/queue", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "pause", jobId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? res.statusText);
      setMsg(`Paused ${jobId.slice(0, 18)}… (Resume from run when ready)`);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const rows: QueueJobRow[] =
    queue?.jobs ??
    jobs.map((j) => ({
      job_id: j.jobId,
      kind: j.kind,
      status: j.status,
      run_id: j.runId,
      error: j.error,
      host: localAlias,
      local: true,
    }));

  const hostOptions =
    hosts.length > 0
      ? hosts
      : [{ alias: localAlias, kind: "local", reachable: true }];

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Jobs / Queue</h2>
        <span className="muted">
          {system?.jobsAllowed ? `fleet launch · ${system.launcher ?? "?"}` : "read-only (PARC_WEB_ALLOW_JOBS=1)"}
          {" · "}
          <Link href="/docs/10_ops_ui">操作マニュアル</Link>
          {" · "}
          <Link href="/docs/11_multi_machine">Fleet</Link>
        </span>
      </header>

      {queue?.counts ? (
        <div className="stat-pills compact">
          {Object.entries(queue.counts).map(([k, v]) => (
            <div key={k}>
              <span className="stat-n">{v}</span>
              <span className="muted">{k}</span>
            </div>
          ))}
        </div>
      ) : null}

      <div className="toolbar wrap">
        <select
          className="input"
          value={targetHost}
          onChange={(e) => setTargetHost(e.target.value)}
          title="Target host"
        >
          {hostOptions.map((h) => (
            <option key={h.alias} value={h.alias}>
              {h.alias}
              {h.reachable === false ? " (down)" : ""}
              {h.kind === "local" || h.alias === localAlias ? " · local" : ""}
            </option>
          ))}
        </select>
        <select
          className="input"
          value={kind}
          onChange={(e) => setKind(e.target.value as JobKind)}
        >
          {(system?.capabilities ?? ["eval", "train", "custom"]).map((k) => (
            <option key={k} value={k}>
              {k === "custom" ? "sweep/prune" : k}
            </option>
          ))}
        </select>
        {(kind === "eval" || kind === "train") && (
          <select className="input grow" value={config} onChange={(e) => setConfig(e.target.value)}>
            {(system?.configs ?? []).map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        )}
        {kind === "custom" && (
          <select className="input grow" value={sweep} onChange={(e) => setSweep(e.target.value)}>
            {(system?.sweeps ?? []).map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        )}
        <button
          className="btn"
          type="button"
          disabled={busy || !system?.jobsAllowed}
          onClick={() => void launch()}
        >
          Launch
        </button>
        <button
          className="btn btn-ghost"
          type="button"
          disabled={busy || !system?.jobsAllowed}
          onClick={() => void queueAction({ action: "recover-stale", maxAgeSec: 3600 })}
        >
          Recover stale (local)
        </button>
        <button
          className="btn btn-ghost"
          type="button"
          disabled={
            busy ||
            !system?.jobsAllowed ||
            !(queue?.counts?.failed || rows.some((r) => r.status === "failed" && (r.local === true || r.host === localAlias)))
          }
          onClick={() => {
            if (!window.confirm("Delete all local failed jobs from the queue? (run dirs kept)")) return;
            void queueAction({ action: "delete", failed: true });
          }}
          title="Remove failed jobs from local queue (run directories are kept)"
        >
          Delete failed (local)
        </button>
      </div>
      {error ? <p className="error">{error}</p> : null}
      {msg ? <p className="muted mono small">{msg}</p> : null}

      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Host</th>
              <th>Job</th>
              <th>Status</th>
              <th>Phase</th>
              <th>Progress</th>
              <th>SR / RL</th>
              <th>Run</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((j) => {
              const phase = j.progress?.phase ?? "";
              const step = j.progress?.step;
              const total = j.progress?.total_steps;
              const pct = j.progress?.percent;
              let progLabel = "—";
              if (step != null && total != null) {
                progLabel = `${step}/${total}`;
                if (pct != null) progLabel += ` (${pct}%)`;
              } else if (pct != null) {
                progLabel = `${pct}%`;
              } else if (phase === "train" || phase === "eval") {
                progLabel = phase;
              }
              const sr =
                j.metrics?.success_rate ??
                j.progress?.metrics?.success_rate ??
                null;
              const rl = j.rl_latest;
              const host = j.host || localAlias;
              const isLocal = j.local === true || host === localAlias;
              return (
                <tr key={`${host}:${j.job_id}`}>
                  <td className="mono muted">{host}</td>
                  <td>
                    <span className="mono">{j.kind}</span>
                    <div className="mono muted small trunc">{j.job_id}</div>
                  </td>
                  <td>
                    <span
                      className={`badge ${
                        j.status === "running"
                          ? "badge-run"
                          : j.status === "failed"
                            ? "badge-bad"
                            : j.status === "done" || j.status === "succeeded"
                              ? "badge-ok"
                              : ""
                      }`}
                    >
                      {j.status}
                      {j.stale ? " stale" : ""}
                    </span>
                  </td>
                  <td className="mono">{phase || "—"}</td>
                  <td className="mono">{progLabel}</td>
                  <td className="mono">
                    {sr != null ? Number(sr).toFixed(3) : "—"}
                    {rl ? (
                      <div className="muted small">
                        u{rl.update} r{Number(rl.mean_reward ?? 0).toFixed(2)}
                      </div>
                    ) : null}
                  </td>
                  <td>
                    {j.run_id && isLocal ? (
                      <Link className="mono" href={`/runs/${encodeURIComponent(j.run_id)}`}>
                        {j.run_id.slice(0, 20)}
                      </Link>
                    ) : j.run_id ? (
                      <span className="mono muted" title="open on remote Web">
                        {j.run_id.slice(0, 20)}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="row-actions">
                    {j.status === "queued" && isLocal && (
                      <button
                        type="button"
                        className="btn btn-tiny"
                        disabled={busy || !system?.jobsAllowed}
                        onClick={() => void cancelJob(j.job_id, host)}
                        title="Remove from queue"
                      >
                        Cancel
                      </button>
                    )}
                    {j.status === "running" && isLocal && (
                      <button
                        type="button"
                        className="btn btn-tiny"
                        disabled={busy || !system?.jobsAllowed}
                        onClick={() => void cancelJob(j.job_id, host)}
                        title="Stop process and free GPU; Resume later from checkpoint"
                      >
                        Pause
                      </button>
                    )}
                    {["failed", "cancelled", "done", "succeeded"].includes(j.status) && isLocal && (
                      <button
                        type="button"
                        className="btn btn-tiny"
                        disabled={busy || !system?.jobsAllowed}
                        onClick={() => void queueAction({ action: "requeue", jobId: j.job_id })}
                      >
                        Requeue
                      </button>
                    )}
                    {["failed", "cancelled", "done", "succeeded"].includes(j.status) && isLocal && (
                      <button
                        type="button"
                        className="btn btn-tiny"
                        disabled={busy || !system?.jobsAllowed}
                        onClick={() => {
                          if (!window.confirm(`Delete job ${j.job_id.slice(0, 18)}… from queue? (run dir kept)`)) {
                            return;
                          }
                          void queueAction({ action: "delete", jobId: j.job_id });
                        }}
                        title="Remove from local queue (run directory is kept)"
                      >
                        Delete
                      </button>
                    )}
                    {j.run_id && isLocal && j.status !== "running" && j.status !== "queued" ? (
                      <button
                        type="button"
                        className="btn btn-tiny"
                        disabled={busy || !system?.jobsAllowed}
                        onClick={() =>
                          void queueAction({ action: "resume", runId: j.run_id, mode: "auto" })
                        }
                        title="Continue from latest checkpoint"
                      >
                        Resume
                      </button>
                    ) : null}
                  </td>
                </tr>
              );
            })}
            {rows.length === 0 ? (
              <tr>
                <td colSpan={8} className="muted">
                  No jobs yet. Worker: <code>uv run parc-worker --loop</code>
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
