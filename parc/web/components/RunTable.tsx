"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import type { RunSummary } from "@/lib/types";

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
};

type FleetHostsResponse = {
  local_alias?: string;
  hosts?: { alias: string; reachable?: boolean; tunnel_hint?: string | null }[];
};

function statusClass(status: string): string {
  if (status === "finished") return "badge badge-ok";
  if (status === "failed") return "badge badge-bad";
  if (status === "running") return "badge badge-run";
  return "badge";
}

function ProgressCell({ run }: { run: RunSummary }) {
  const p = run.progress;
  if (!p || p.label === "—") {
    return <span className="muted">—</span>;
  }
  const showBar = p.percent != null && run.status === "running";
  return (
    <div className="run-progress">
      <div className="run-progress-label mono">
        {p.label}
        {p.percent != null && run.status === "running" ? (
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

function mapFleetRun(row: FleetRunRow): RunSummary {
  const metrics = (row as { metrics?: { success_rate?: number } }).metrics;
  const rawSr = row.success_rate ?? metrics?.success_rate;
  const sr =
    rawSr == null || Number.isNaN(Number(rawSr)) ? null : Number(rawSr);
  const tags = Array.isArray(row.tags) ? row.tags : [];
  return {
    runId: String(row.run_id ?? ""),
    name: String(row.name ?? ""),
    createdAt: String(row.created_at ?? ""),
    status: String(row.status ?? "created"),
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
    progress: null,
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

  useEffect(() => {
    setRuns(initialRuns);
  }, [initialRuns]);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        if (fleetMode) {
          const [runsRes, hostsRes] = await Promise.all([
            fetch("/api/v1/fleet/runs?limit=100"),
            fetch("/api/v1/fleet/hosts"),
          ]);
          if (!alive) return;
          if (runsRes.ok) {
            const data = (await runsRes.json()) as {
              runs?: FleetRunRow[];
              errors?: Record<string, string>;
            };
            if (data.runs) {
              setRuns(data.runs.map(mapFleetRun));
            }
            setFleetErrors(data.errors ?? {});
          }
          if (hostsRes.ok) {
            const h = (await hostsRes.json()) as FleetHostsResponse;
            const aliases = (h.hosts ?? []).map((x) => x.alias);
            setHostAliases(aliases);
            const hints: Record<string, string> = {};
            for (const row of h.hosts ?? []) {
              if (row.tunnel_hint) hints[row.alias] = row.tunnel_hint;
            }
            setTunnelHints(hints);
          }
          setUpdatedAt(new Date().toLocaleTimeString());
          return;
        }
        const res = await fetch("/api/v1/runs?limit=100");
        if (!res.ok) return;
        const data = (await res.json()) as { runs?: RunSummary[] };
        if (!alive || !data.runs) return;
        setRuns(data.runs);
        setUpdatedAt(new Date().toLocaleTimeString());
      } catch {
        /* ignore */
      }
    };
    void tick();
    const id = window.setInterval(() => {
      void tick();
    }, 8000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [fleetMode]);

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
    const hay = `${r.runId} ${r.name} ${r.host ?? ""} ${r.machineId ?? ""} ${r.tags.join(" ")} ${r.progress?.label ?? ""}`.toLowerCase();
    if (q && !hay.includes(q.toLowerCase())) return false;
    if (tag && !r.tags.includes(tag)) return false;
    if (hostFilter) {
      const h = r.host || r.machineId || "";
      if (h !== hostFilter) return false;
    }
    return true;
  });

  const runningCount = runs.filter((r) => r.status === "running").length;
  const errorHosts = Object.keys(fleetErrors);

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
        <span className="muted">
          {filtered.length} / {runs.length}
        </span>
        {runningCount > 0 ? (
          <span className="badge badge-run">{runningCount} running</span>
        ) : null}
        {updatedAt ? <span className="muted">updated {updatedAt}</span> : null}
      </div>

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
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => {
              const host = r.host || r.machineId || "—";
              const canOpen = r.local !== false;
              return (
                <tr
                  key={`${host}:${r.runId}`}
                  className={r.status === "running" ? "row-running" : undefined}
                >
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
                </tr>
              );
            })}
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="muted">
                  No runs match.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
