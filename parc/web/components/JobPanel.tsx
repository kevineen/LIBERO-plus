"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import type { JobHandle, JobKind } from "@/lib/types";

type QueueJobRow = {
  job_id: string;
  kind: string;
  status: string;
  stale?: boolean;
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

export function JobPanel() {
  const [jobs, setJobs] = useState<JobHandle[]>([]);
  const [queue, setQueue] = useState<QueueStatus | null>(null);
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [kind, setKind] = useState<JobKind>("train");
  const [config, setConfig] = useState("");
  const [sweep, setSweep] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [j, s, q] = await Promise.all([
      fetch("/api/v1/jobs?limit=30").then((r) => r.json()),
      fetch("/api/v1/system").then((r) => r.json()),
      fetch("/api/v1/queue?limit=40").then((r) => r.json()).catch(() => null),
    ]);
    setJobs(j.jobs ?? []);
    setQueue(q && !q.error ? q : null);
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
    const t = setInterval(() => void refresh(), 5000);
    return () => clearInterval(t);
  }, [refresh]);

  async function launch() {
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const body: Record<string, unknown> = { kind };
      if (kind === "custom" && sweep) {
        body.params = { sweep: sweep.startsWith("configs/") ? sweep : `configs/sweeps/${sweep}` };
      } else if (kind === "eval" || kind === "train") {
        body.configPath = config;
      }
      const res = await fetch("/api/v1/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? res.statusText);
      setMsg(`queued ${data.job?.jobId ?? ""}`);
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

  async function cancelJob(jobId: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/jobs/${encodeURIComponent(jobId)}`, { method: "DELETE" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? res.statusText);
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
    }));

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Jobs / Queue</h2>
        <span className="muted">
          {system?.jobsAllowed ? `launch on · ${system.launcher ?? "?"}` : "read-only (PARC_WEB_ALLOW_JOBS=1)"}
          {" · "}
          <Link href="/docs/10_ops_ui">操作マニュアル</Link>
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
          {(queue.stale_running?.length ?? 0) > 0 ? (
            <div>
              <span className="stat-n warn">{queue.stale_running!.length}</span>
              <span className="muted">stale</span>
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="toolbar wrap">
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
          Recover stale
        </button>
      </div>
      {error ? <p className="error">{error}</p> : null}
      {msg ? <p className="muted mono small">{msg}</p> : null}

      {(queue?.top_scores?.length ?? 0) > 0 ? (
        <div className="score-strip">
          <strong>Top scores</strong>
          <ul>
            {queue!.top_scores!.map((s) => (
              <li key={`${s.job_id}-${s.run_id}`}>
                {s.run_id ? (
                  <Link href={`/runs/${encodeURIComponent(s.run_id)}`}>{s.run_id.slice(0, 22)}</Link>
                ) : (
                  "—"
                )}
                <span className="mono">
                  {s.success_rate == null ? "—" : Number(s.success_rate).toFixed(3)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
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
              return (
                <tr key={j.job_id}>
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
                    {j.run_id ? (
                      <Link className="mono" href={`/runs/${encodeURIComponent(j.run_id)}`}>
                        {j.run_id.slice(0, 20)}
                      </Link>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="row-actions">
                    {(j.status === "queued" || j.status === "running") && (
                      <button
                        type="button"
                        className="btn btn-tiny"
                        disabled={busy || !system?.jobsAllowed}
                        onClick={() => void cancelJob(j.job_id)}
                      >
                        Cancel
                      </button>
                    )}
                    {["failed", "cancelled", "done", "succeeded"].includes(j.status) && (
                      <button
                        type="button"
                        className="btn btn-tiny"
                        disabled={busy || !system?.jobsAllowed}
                        onClick={() => void queueAction({ action: "requeue", jobId: j.job_id })}
                      >
                        Requeue
                      </button>
                    )}
                    {j.run_id ? (
                      <button
                        type="button"
                        className="btn btn-tiny"
                        disabled={busy || !system?.jobsAllowed}
                        onClick={() =>
                          void queueAction({ action: "resume", runId: j.run_id, mode: "auto" })
                        }
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
                <td colSpan={6} className="muted">
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
