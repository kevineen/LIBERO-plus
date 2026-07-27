"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { RunSummary } from "@/lib/types";

type FleetRunProgress = {
  phase?: string;
  label?: string;
  percent?: number | null;
  step?: number | null;
  total_steps?: number | null;
  totalSteps?: number | null;
  job_id?: string | null;
  jobId?: string | null;
  job_status?: string | null;
  jobStatus?: string | null;
};

type FleetRunRow = {
  run_id?: string;
  name?: string;
  created_at?: string;
  status?: string;
  tags?: string[];
  notes?: string;
  machine_id?: string;
  host?: string;
  local?: boolean;
  success_rate?: number | null;
  sweep_id?: string;
  progress?: FleetRunProgress | null;
};

type FleetHostsResponse = {
  local_alias?: string;
  hosts?: { alias: string; reachable?: boolean; tunnel_hint?: string | null }[];
};

/** Pause 残骸・失敗など、一覧から消してよい終端ステータス */
const DELETABLE_STATUSES = new Set(["failed", "paused", "created", "cancelled"]);

function isPausedLike(status: string): boolean {
  const s = status.toLowerCase();
  return s === "paused" || s === "stop" || s === "stopped" || s === "cancelled";
}

function statusClass(status: string): string {
  if (status === "finished") return "badge badge-ok";
  if (status === "failed") return "badge badge-bad";
  if (status === "running") return "badge badge-run";
  if (isPausedLike(status)) return "badge";
  return "badge";
}

function isActivelyRunning(run: RunSummary): boolean {
  return run.status === "running" || run.progress?.jobStatus === "running";
}

function ProgressCell({ run }: { run: RunSummary }) {
  const p = run.progress;
  if (!p || p.label === "—") {
    return <span className="muted">—</span>;
  }
  const active = isActivelyRunning(run);
  const showBar = p.percent != null && active;
  return (
    <div className="run-progress">
      <div className="run-progress-label mono">
        {p.label}
        {p.percent != null && active ? (
          <span className="muted"> · {p.percent}%</span>
        ) : null}
      </div>
      {showBar ? (
        <div className="run-progress-track" title={`${p.percent}%`}>
          <div className="run-progress-fill" style={{ width: `${p.percent}%` }} />
        </div>
      ) : null}
    </div>
  );
}

function mapFleetProgress(p: FleetRunProgress | null | undefined, status: string) {
  if (!p) return null;
  const phase = String(p.phase || status || "unknown");
  const label = String(p.label || "—");
  if (label === "—") return null;
  const percent =
    p.percent == null || Number.isNaN(Number(p.percent))
      ? null
      : Math.max(0, Math.min(100, Math.round(Number(p.percent))));
  const step = p.step == null || Number.isNaN(Number(p.step)) ? null : Number(p.step);
  const totalRaw = p.total_steps ?? p.totalSteps;
  const totalSteps =
    totalRaw == null || Number.isNaN(Number(totalRaw)) ? null : Number(totalRaw);
  return {
    phase,
    label,
    percent,
    step,
    totalSteps,
    jobId: p.job_id ?? p.jobId ?? null,
    jobStatus: p.job_status ?? p.jobStatus ?? null,
  };
}

function mapFleetRun(row: FleetRunRow): RunSummary {
  const metrics = (row as { metrics?: { success_rate?: number } }).metrics;
  const rawSr = row.success_rate ?? metrics?.success_rate;
  const sr =
    rawSr == null || Number.isNaN(Number(rawSr)) ? null : Number(rawSr);
  const tags = Array.isArray(row.tags) ? row.tags : [];
  const status = String(row.status ?? "created");
  return {
    runId: String(row.run_id ?? ""),
    name: String(row.name ?? ""),
    createdAt: String(row.created_at ?? ""),
    status,
    tags,
    notes: String(row.notes ?? ""),
    machineId: row.machine_id ? String(row.machine_id) : null,
    host: row.host ? String(row.host) : null,
    local: Boolean(row.local),
    successRate: sr,
    nEpisodes: null,
    hasMetrics: sr != null,
    hasVideos: false,
    hasCheckpoints: false,
    progress: mapFleetProgress(row.progress, status),
  };
}

export function RunTable({ runs: initialRuns }: { runs: RunSummary[] }) {
  const [runs, setRuns] = useState(initialRuns);
  const [q, setQ] = useState("");
  const [tag, setTag] = useState("");
  const [hostFilter, setHostFilter] = useState("");
  const [hostAliases, setHostAliases] = useState<string[]>([]);
  const [tunnelHints, setTunnelHints] = useState<Record<string, string>>({});
  const [fleetErrors, setFleetErrors] = useState<Record<string, string>>({});
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [fleetMode, setFleetMode] = useState(true);
  /** Pause 残骸はデフォルト非表示（Resume 済みの stop/paused） */
  const [hidePaused, setHidePaused] = useState(true);
  const [jobsAllowed, setJobsAllowed] = useState(false);
  const [localAlias, setLocalAlias] = useState("local");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      if (fleetMode) {
        const [runsRes, hostsRes, sysRes] = await Promise.all([
          fetch("/api/v1/fleet/runs?limit=100"),
          fetch("/api/v1/fleet/hosts"),
          fetch("/api/v1/system"),
        ]);
        if (runsRes.ok) {
          const data = (await runsRes.json()) as {
            runs?: FleetRunRow[];
            errors?: Record<string, string>;
            local_alias?: string;
          };
          if (data.runs) setRuns(data.runs.map(mapFleetRun));
          setFleetErrors(data.errors ?? {});
          if (data.local_alias) setLocalAlias(String(data.local_alias));
        }
        if (hostsRes.ok) {
          const h = (await hostsRes.json()) as FleetHostsResponse & { local_alias?: string };
          const aliases = (h.hosts ?? []).map((x) => x.alias);
          setHostAliases(aliases);
          if (h.local_alias) setLocalAlias(String(h.local_alias));
          const hints: Record<string, string> = {};
          for (const row of h.hosts ?? []) {
            if (row.tunnel_hint) hints[row.alias] = row.tunnel_hint;
          }
          setTunnelHints(hints);
        }
        if (sysRes.ok) {
          const s = (await sysRes.json()) as { jobsAllowed?: boolean };
          setJobsAllowed(!!s.jobsAllowed);
        }
        setUpdatedAt(new Date().toLocaleTimeString());
        return;
      }
      const [res, sysRes] = await Promise.all([
        fetch("/api/v1/runs?limit=100"),
        fetch("/api/v1/system"),
      ]);
      if (res.ok) {
        const data = (await res.json()) as { runs?: RunSummary[] };
        if (data.runs) setRuns(data.runs);
      }
      if (sysRes.ok) {
        const s = (await sysRes.json()) as { jobsAllowed?: boolean };
        setJobsAllowed(!!s.jobsAllowed);
      }
      setUpdatedAt(new Date().toLocaleTimeString());
    } catch {
      /* ignore */
    }
  }, [fleetMode]);

  useEffect(() => {
    setRuns(initialRuns);
  }, [initialRuns]);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      if (!alive) return;
      await refresh();
    };
    void tick();
    const id = window.setInterval(() => {
      void tick();
    }, 8000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [refresh]);

  async function deleteRuns(payload: Record<string, unknown>) {
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const res = await fetch("/api/v1/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "delete", ...payload }),
      });
      const data = (await res.json()) as { error?: string; result?: { count?: number } };
      if (!res.ok) throw new Error(data.error ?? res.statusText);
      setMsg(`deleted ${data.result?.count ?? "?"} run(s)`);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const tags = useMemo(() => {
    const s = new Set<string>();
    runs.forEach((r) => r.tags.forEach((t) => s.add(t)));
    return [...s].sort();
  }, [runs]);

  const hosts = useMemo(() => {
    const s = new Set<string>(hostAliases);
    runs.forEach((r) => {
      if (r.host) s.add(r.host);
      else if (r.machineId) s.add(r.machineId);
    });
    return [...s].sort();
  }, [runs, hostAliases]);

  const filtered = runs.filter((r) => {
    if (hidePaused && isPausedLike(r.status)) return false;
    const hay = `${r.runId} ${r.name} ${r.host ?? ""} ${r.machineId ?? ""} ${r.tags.join(" ")} ${r.progress?.label ?? ""}`.toLowerCase();
    if (q && !hay.includes(q.toLowerCase())) return false;
    if (tag && !r.tags.includes(tag)) return false;
    if (hostFilter) {
      const h = r.host || r.machineId || "";
      if (h !== hostFilter) return false;
    }
    return true;
  });

  /** 実行中だけ上部カードに出す（一覧テーブルからも除外して重複を避ける） */
  const runningRuns = filtered.filter(isActivelyRunning);
  const tableRuns = filtered.filter((r) => !isActivelyRunning(r));
  const runningCount = runs.filter(isActivelyRunning).length;
  const localFailed = runs.filter(
    (r) => r.status === "failed" && (r.local === true || r.host === localAlias || !r.host),
  ).length;
  const localPaused = runs.filter(
    (r) => isPausedLike(r.status) && (r.local === true || r.host === localAlias || !r.host),
  ).length;
  const errorHosts = Object.keys(fleetErrors);
  const hiddenPaused = hidePaused
    ? runs.filter((r) => isPausedLike(r.status)).length
    : 0;

  return (
    <div className="stack">
      <div className="toolbar wrap">
        <input
          className="input"
          placeholder="Filter runs…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select className="input" value={hostFilter} onChange={(e) => setHostFilter(e.target.value)}>
          <option value="">All hosts</option>
          {hosts.map((h) => (
            <option key={h} value={h}>
              {h}
            </option>
          ))}
        </select>
        <select className="input" value={tag} onChange={(e) => setTag(e.target.value)}>
          <option value="">All tags</option>
          {tags.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <label className="muted" style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <input
            type="checkbox"
            checked={fleetMode}
            onChange={(e) => setFleetMode(e.target.checked)}
          />
          Fleet
        </label>
        <label className="muted" style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <input
            type="checkbox"
            checked={hidePaused}
            onChange={(e) => setHidePaused(e.target.checked)}
          />
          Hide paused
          {hiddenPaused > 0 ? ` (${hiddenPaused})` : ""}
        </label>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={busy || !jobsAllowed || localFailed === 0}
          onClick={() => {
            if (!window.confirm(`Delete ${localFailed} local failed run(s)? (directories removed)`)) {
              return;
            }
            void deleteRuns({ failed: true });
          }}
          title="Remove local failed experiment directories"
        >
          Delete failed
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={busy || !jobsAllowed || localPaused === 0}
          onClick={() => {
            if (
              !window.confirm(
                `Delete ${localPaused} local paused run(s)? (Pause leftovers after Resume)`,
              )
            ) {
              return;
            }
            void deleteRuns({ paused: true });
          }}
          title="Remove local paused/stop leftovers"
        >
          Delete paused
        </button>
        <span className="muted">
          {filtered.length} / {runs.length}
        </span>
        {runningCount > 0 ? (
          <span className="badge badge-run">{runningCount} running</span>
        ) : null}
        {updatedAt ? <span className="muted">updated {updatedAt}</span> : null}
      </div>

      {error ? <p className="error small">{error}</p> : null}
      {msg ? <p className="muted mono small">{msg}</p> : null}

      {errorHosts.length > 0 ? (
        <p className="error small">
          Unreachable: {errorHosts.join(", ")}
          {hostFilter && tunnelHints[hostFilter] ? (
            <>
              {" · tunnel: "}
              <code className="mono">{tunnelHints[hostFilter].split("\n")[0]}</code>
            </>
          ) : null}
        </p>
      ) : null}

      {runningRuns.length > 0 ? (
        <div className="running-cards" aria-label="Running runs">
          {runningRuns.map((r) => {
            const host = r.host || r.machineId || "—";
            const canOpen = r.local !== false;
            const body = (
              <>
                <div className="running-card-head">
                  <span className="running-card-title">{r.name || r.runId}</span>
                  <span className={statusClass(r.status)}>{r.status}</span>
                </div>
                <div className="running-card-meta">
                  <span className="mono muted">{host}</span>
                  <span className="mono muted trunc" title={r.runId}>
                    {r.runId.slice(0, 28)}
                    {r.runId.length > 28 ? "…" : ""}
                  </span>
                </div>
                <ProgressCell run={r} />
              </>
            );
            return canOpen || r.local ? (
              <Link
                key={`${host}:${r.runId}`}
                className="running-card"
                href={`/runs/${encodeURIComponent(r.runId)}`}
              >
                {body}
              </Link>
            ) : (
              <div key={`${host}:${r.runId}`} className="running-card">
                {body}
                <div className="muted small">
                  remote — open Web on {host}
                  {tunnelHints[host] ? (
                    <>
                      {" "}
                      (<code className="mono">{tunnelHints[host].split("\n")[0]}</code>)
                    </>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      ) : null}

      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Run</th>
              <th>Host</th>
              <th>Status</th>
              <th>Progress</th>
              <th>SR</th>
              <th>Eps</th>
              <th>Flags</th>
              <th>Tags</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {tableRuns.map((r) => {
              const host = r.host || r.machineId || "—";
              const isLocal = r.local === true || host === localAlias || !r.host;
              const canOpen = r.local !== false;
              const canDelete = isLocal && DELETABLE_STATUSES.has(r.status);
              return (
                <tr key={`${host}:${r.runId}`}>
                  <td>
                    {canOpen || r.local ? (
                      <Link className="run-link" href={`/runs/${encodeURIComponent(r.runId)}`}>
                        <span className="run-name">{r.name}</span>
                        <span className="mono muted">{r.runId}</span>
                      </Link>
                    ) : (
                      <div className="run-link">
                        <span className="run-name">{r.name}</span>
                        <span className="mono muted">{r.runId}</span>
                        <div className="muted small">
                          remote — open Web on {host}
                          {tunnelHints[host] ? (
                            <>
                              {" "}
                              (<code className="mono">{tunnelHints[host].split("\n")[0]}</code>)
                            </>
                          ) : null}
                        </div>
                      </div>
                    )}
                  </td>
                  <td className="mono muted">{host}</td>
                  <td>
                    <span className={statusClass(r.status)}>{r.status}</span>
                  </td>
                  <td>
                    <ProgressCell run={r} />
                  </td>
                  <td className="mono">
                    {r.successRate == null ? "—" : r.successRate.toFixed(3)}
                  </td>
                  <td className="mono">{r.nEpisodes ?? "—"}</td>
                  <td className="flags">
                    {r.hasMetrics ? <span title="metrics">M</span> : null}
                    {r.hasVideos ? <span title="videos">V</span> : null}
                    {r.hasCheckpoints ? <span title="checkpoints">C</span> : null}
                  </td>
                  <td className="tags">
                    {r.tags.map((t) => (
                      <span key={t} className="tag">
                        {t}
                      </span>
                    ))}
                  </td>
                  <td className="row-actions">
                    {canDelete ? (
                      <button
                        type="button"
                        className="btn btn-tiny"
                        disabled={busy || !jobsAllowed}
                        onClick={() => {
                          if (
                            !window.confirm(
                              `Delete run ${r.runId.slice(0, 24)}…? (directory removed)`,
                            )
                          ) {
                            return;
                          }
                          void deleteRuns({ runId: r.runId });
                        }}
                        title="Delete experiment directory"
                      >
                        Delete
                      </button>
                    ) : null}
                  </td>
                </tr>
              );
            })}
            {tableRuns.length === 0 ? (
              <tr>
                <td colSpan={9} className="muted">
                  {runningRuns.length > 0
                    ? "No other runs (running ones are in cards above)."
                    : "No runs match."}
                  {hidePaused && hiddenPaused > 0 && runningRuns.length === 0
                    ? ` (${hiddenPaused} paused hidden — uncheck “Hide paused”)`
                    : ""}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
