"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import type { RunSummary } from "@/lib/types";

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

export function RunTable({ runs: initialRuns }: { runs: RunSummary[] }) {
  const [runs, setRuns] = useState(initialRuns);
  const [q, setQ] = useState("");
  const [tag, setTag] = useState("");
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);

  useEffect(() => {
    setRuns(initialRuns);
  }, [initialRuns]);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
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
    }, 5000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);

  const tags = useMemo(() => {
    const s = new Set<string>();
    runs.forEach((r) => r.tags.forEach((t) => s.add(t)));
    return [...s].sort();
  }, [runs]);

  const filtered = runs.filter((r) => {
    const hay = `${r.runId} ${r.name} ${r.machineId ?? ""} ${r.tags.join(" ")} ${r.progress?.label ?? ""}`.toLowerCase();
    if (q && !hay.includes(q.toLowerCase())) return false;
    if (tag && !r.tags.includes(tag)) return false;
    return true;
  });

  const runningCount = runs.filter((r) => r.status === "running").length;

  return (
    <div className="stack">
      <div className="toolbar">
        <input
          className="input"
          placeholder="Filter runs…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select className="input" value={tag} onChange={(e) => setTag(e.target.value)}>
          <option value="">All tags</option>
          {tags.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <span className="muted">{filtered.length} / {runs.length}</span>
        {runningCount > 0 ? (
          <span className="badge badge-run">{runningCount} running</span>
        ) : null}
        {updatedAt ? <span className="muted">updated {updatedAt}</span> : null}
      </div>

      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Run</th>
              <th>Machine</th>
              <th>Status</th>
              <th>Progress</th>
              <th>SR</th>
              <th>Eps</th>
              <th>Flags</th>
              <th>Tags</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr key={r.runId} className={r.status === "running" ? "row-running" : undefined}>
                <td>
                  <Link className="run-link" href={`/runs/${encodeURIComponent(r.runId)}`}>
                    <span className="run-name">{r.name}</span>
                    <span className="mono muted">{r.runId}</span>
                  </Link>
                </td>
                <td className="mono muted">{r.machineId ?? "—"}</td>
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
            ))}
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
