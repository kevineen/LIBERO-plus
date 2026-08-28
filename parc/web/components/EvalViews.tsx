"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import type { EvalRunDetail, EvalRunSummary, EvalTask } from "@/lib/types";

function statusClass(status: string): string {
  if (status === "finished") return "badge badge-ok";
  if (status === "running") return "badge badge-run";
  return "badge";
}

function fmtRate(rate: number | null): string {
  if (rate == null) return "—";
  return `${(rate * 100).toFixed(1)}%`;
}

function fmtDuration(seconds: number | null): string {
  if (seconds == null || !Number.isFinite(seconds)) return "—";
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export function EvalListView() {
  const [runs, setRuns] = useState<EvalRunSummary[]>([]);
  const [dir, setDir] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchJson<{ runs: EvalRunSummary[]; evalLogsDir: string }>("/api/v1/evals");
      setRuns(data.runs);
      setDir(data.evalLogsDir);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load evals");
    }
  }, []);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(id);
  }, [load]);

  const running = runs.filter((r) => r.status === "running");

  return (
    <div className="page">
      <section className="hero-band">
        <div>
          <p className="eyebrow">LIBERO-plus · eval monitor</p>
          <h1>Evals</h1>
          <p className="lede">
            <code className="mono">{dir || "eval_logs"}</code>
            {" · "}タスクを1件ずつ開いてエピソード動画を確認できます
          </p>
        </div>
        <div className="stat-pills">
          <div>
            <span className="stat-n">{runs.length}</span>
            <span className="muted">runs</span>
          </div>
          <div>
            <span className="stat-n">{running.length}</span>
            <span className="muted">running</span>
          </div>
        </div>
      </section>

      {error ? <p className="error">{error}</p> : null}

      {running.length > 0 ? (
        <div className="running-cards">
          {running.map((r) => (
            <Link key={r.runId} href={`/evals/${encodeURIComponent(r.runId)}`} className="running-card">
              <div className="running-card-head">
                <span className="running-card-title">{r.runId}</span>
                <span className={statusClass(r.status)}>{r.status}</span>
              </div>
              <div className="run-progress">
                <div className="run-progress-label mono">
                  {r.completedTasks}
                  {r.totalTasks != null ? `/${r.totalTasks}` : ""} tasks
                  {r.percent != null ? <span className="muted"> · {r.percent}%</span> : null}
                </div>
                {r.percent != null ? (
                  <div className="run-progress-track">
                    <div className="run-progress-fill" style={{ width: `${r.percent}%` }} />
                  </div>
                ) : null}
              </div>
            </Link>
          ))}
        </div>
      ) : null}

      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Run</th>
              <th>Status</th>
              <th>Progress</th>
              <th>Success</th>
              <th>Episodes</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {runs.length === 0 ? (
              <tr>
                <td colSpan={6} className="muted">
                  eval_logs に実行がありません。
                </td>
              </tr>
            ) : (
              runs.map((r) => (
                <tr key={r.runId} className={r.status === "running" ? "row-running" : undefined}>
                  <td>
                    <Link href={`/evals/${encodeURIComponent(r.runId)}`} className="run-link">
                      <span className="run-name">{r.runId}</span>
                      <span className="muted mono small">{r.hasVideos ? "videos" : "no videos"}</span>
                    </Link>
                  </td>
                  <td>
                    <span className={statusClass(r.status)}>{r.status}</span>
                  </td>
                  <td className="mono">
                    {r.completedTasks}
                    {r.totalTasks != null ? `/${r.totalTasks}` : ""}
                    {r.percent != null ? ` · ${r.percent}%` : ""}
                  </td>
                  <td className="mono">{fmtRate(r.successRate)}</td>
                  <td className="mono">{r.nEpisodes}</td>
                  <td className="muted small">{r.updatedAt.replace("T", " ").slice(0, 19)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function EvalDetailView({ runId }: { runId: string }) {
  const [run, setRun] = useState<EvalRunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchJson<{ run: EvalRunDetail }>(
        `/api/v1/evals/${encodeURIComponent(runId)}`
      );
      setRun(data.run);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load eval");
    }
  }, [runId]);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(id);
  }, [load]);

  if (error && !run) {
    return <p className="error">{error}</p>;
  }
  if (!run) {
    return <p className="muted">読み込み中…</p>;
  }

  return (
    <div className="page">
      <p className="crumb">
        <Link href="/evals">Evals</Link> / <span className="mono">{run.runId}</span>
      </p>

      <header className="detail-head">
        <div>
          <h1>{run.runId}</h1>
          <p className="muted mono">{run.runDir}</p>
        </div>
        <div className="detail-stats">
          <div>
            <span className="muted">status</span>
            <strong>
              <span className={statusClass(run.status)}>{run.status}</span>
            </strong>
          </div>
          <div>
            <span className="muted">success</span>
            <strong className="mono">{fmtRate(run.successRate)}</strong>
          </div>
          <div>
            <span className="muted">episodes</span>
            <strong className="mono">{run.nEpisodes}</strong>
          </div>
          <div>
            <span className="muted">elapsed</span>
            <strong className="mono">{fmtDuration(run.evalS)}</strong>
          </div>
        </div>
      </header>

      <section className="panel">
        <header className="panel-head">
          <h2>Progress</h2>
          <span className="muted mono">
            {run.completedTasks}
            {run.totalTasks != null ? `/${run.totalTasks}` : ""} tasks
            {run.percent != null ? ` · ${run.percent}%` : ""}
          </span>
        </header>
        {run.percent != null ? (
          <div className="run-progress">
            <div className="run-progress-track">
              <div className="run-progress-fill" style={{ width: `${run.percent}%` }} />
            </div>
          </div>
        ) : (
          <p className="muted">タスク完了数がまだ揃っていません（動画スキャン中）。</p>
        )}
      </section>

      <section className="panel">
        <header className="panel-head">
          <h2>Suites</h2>
        </header>
        {run.groups.length === 0 ? (
          <p className="muted">スイート集計がまだありません。</p>
        ) : (
          <div className="cat-list">
            {run.groups.map((g) => (
              <div key={g.taskGroup} className="cat-row">
                <div className="cat-label">
                  <Link href={`/evals/${encodeURIComponent(run.runId)}/suites/${encodeURIComponent(g.taskGroup)}`}>
                    {g.taskGroup}
                  </Link>
                  <span className="mono muted">
                    tasks={g.nTasks} · n={g.nEpisodes} · sr={fmtRate(g.successRate)}
                  </span>
                </div>
                <div className="bar-track">
                  <div
                    className="bar-fill"
                    style={{
                      width: `${Math.max(0, Math.min(1, g.successRate ?? 0)) * 100}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <header className="panel-head">
          <h2>Tasks</h2>
          <span className="muted">1件ずつ開く</span>
        </header>
        {run.tasks.length === 0 ? (
          <p className="muted">完了したタスクはまだありません。</p>
        ) : (
          <ul className="task-grid">
            {run.tasks.map((t) => (
              <li key={t.taskKey}>
                <Link
                  href={`/evals/${encodeURIComponent(run.runId)}/tasks/${encodeURIComponent(t.taskKey)}`}
                  className="task-card"
                >
                  <span className="task-card-title mono">
                    {t.taskGroup} #{t.taskId}
                  </span>
                  <span className="muted small">
                    {t.nSuccess}/{t.nEpisodes} ok · {fmtRate(t.successRate)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export function EvalSuiteView({ runId, suite }: { runId: string; suite: string }) {
  const [run, setRun] = useState<EvalRunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchJson<{ run: EvalRunDetail }>(
        `/api/v1/evals/${encodeURIComponent(runId)}`
      );
      setRun(data.run);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load eval");
    }
  }, [runId]);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(id);
  }, [load]);

  if (error && !run) return <p className="error">{error}</p>;
  if (!run) return <p className="muted">読み込み中…</p>;

  const suites = [...new Set(run.tasks.map((t) => t.taskGroup))];
  const suiteIdx = suites.indexOf(suite);
  const prevSuite = suiteIdx > 0 ? suites[suiteIdx - 1] : null;
  const nextSuite = suiteIdx >= 0 && suiteIdx < suites.length - 1 ? suites[suiteIdx + 1] : null;
  const tasks = run.tasks.filter((t) => t.taskGroup === suite);
  const group = run.groups.find((g) => g.taskGroup === suite);
  const suiteRate = group?.successRate ?? rateFromTasks(tasks);

  return (
    <div className="page">
      <p className="crumb">
        <Link href="/evals">Evals</Link>
        {" / "}
        <Link href={`/evals/${encodeURIComponent(run.runId)}`}>{run.runId}</Link>
        {" / "}
        <span className="mono">{suite}</span>
      </p>

      <header className="detail-head">
        <div>
          <h1>{suite}</h1>
          <p className="muted">
            {tasks.length} tasks
            {group ? ` · n=${group.nEpisodes}` : ""}
            {" · "}
            {fmtRate(suiteRate)}
          </p>
        </div>
        <div className="toolbar">
          {prevSuite ? (
            <Link
              className="btn btn-ghost"
              href={`/evals/${encodeURIComponent(run.runId)}/suites/${encodeURIComponent(prevSuite)}`}
            >
              ← {prevSuite}
            </Link>
          ) : (
            <button type="button" className="btn btn-ghost" disabled>
              ← prev
            </button>
          )}
          {nextSuite ? (
            <Link
              className="btn"
              href={`/evals/${encodeURIComponent(run.runId)}/suites/${encodeURIComponent(nextSuite)}`}
            >
              {nextSuite} →
            </Link>
          ) : (
            <button type="button" className="btn" disabled>
              next →
            </button>
          )}
        </div>
      </header>

      <section className="panel">
        <header className="panel-head">
          <h2>Tasks</h2>
        </header>
        {tasks.length === 0 ? (
          <p className="muted">このスイートのタスクはまだありません。</p>
        ) : (
          <ul className="task-grid">
            {tasks.map((t) => (
              <li key={t.taskKey}>
                <Link
                  href={`/evals/${encodeURIComponent(run.runId)}/tasks/${encodeURIComponent(t.taskKey)}`}
                  className="task-card"
                >
                  <span className="task-card-title mono">#{t.taskId}</span>
                  <span className="muted small">
                    {t.nSuccess}/{t.nEpisodes} ok · {fmtRate(t.successRate)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function rateFromTasks(tasks: EvalTask[]): number | null {
  const known = tasks.flatMap((t) => t.episodes.map((e) => e.success)).filter((s): s is boolean => s !== null);
  if (known.length === 0) return null;
  return known.filter(Boolean).length / known.length;
}

export function EvalTaskView({ runId, taskKey }: { runId: string; taskKey: string }) {
  const [run, setRun] = useState<EvalRunDetail | null>(null);
  const [epIndex, setEpIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchJson<{ run: EvalRunDetail }>(
        `/api/v1/evals/${encodeURIComponent(runId)}`
      );
      setRun(data.run);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load eval");
    }
  }, [runId]);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(id);
  }, [load]);

  // タスクを切り替えたらエピソード選択を先頭に戻す
  useEffect(() => {
    setEpIndex(0);
  }, [taskKey]);

  if (error && !run) return <p className="error">{error}</p>;
  if (!run) return <p className="muted">読み込み中…</p>;

  const idx = run.tasks.findIndex((t) => t.taskKey === taskKey);
  const task: EvalTask | undefined = idx >= 0 ? run.tasks[idx] : undefined;
  if (!task) {
    return (
      <div className="page">
        <p className="crumb">
          <Link href="/evals">Evals</Link> /{" "}
          <Link href={`/evals/${encodeURIComponent(runId)}`}>{runId}</Link>
        </p>
        <p className="error">タスク {taskKey} が見つかりません。</p>
      </div>
    );
  }

  const suiteTasks = run.tasks.filter((t) => t.taskGroup === task.taskGroup);
  const suiteIdx = suiteTasks.findIndex((t) => t.taskKey === task.taskKey);
  const prev = suiteIdx > 0 ? suiteTasks[suiteIdx - 1] : null;
  const next = suiteIdx < suiteTasks.length - 1 ? suiteTasks[suiteIdx + 1] : null;
  const episode = task.episodes[Math.min(epIndex, Math.max(0, task.episodes.length - 1))];

  return (
    <div className="page">
      <p className="crumb">
        <Link href="/evals">Evals</Link>
        {" / "}
        <Link href={`/evals/${encodeURIComponent(run.runId)}`}>{run.runId}</Link>
        {" / "}
        <Link href={`/evals/${encodeURIComponent(run.runId)}/suites/${encodeURIComponent(task.taskGroup)}`}>
          {task.taskGroup}
        </Link>
        {" / "}
        <span className="mono">#{task.taskId}</span>
      </p>

      <header className="detail-head">
        <div>
          <h1>
            {task.taskGroup} #{task.taskId}
          </h1>
          <p className="muted">
            {suiteIdx + 1} / {suiteTasks.length} in {task.taskGroup} · success {fmtRate(task.successRate)}
          </p>
        </div>
        <div className="toolbar">
          {prev ? (
            <Link
              className="btn btn-ghost"
              href={`/evals/${encodeURIComponent(run.runId)}/tasks/${encodeURIComponent(prev.taskKey)}`}
            >
              ← #{prev.taskId}
            </Link>
          ) : (
            <button type="button" className="btn btn-ghost" disabled>
              ← prev
            </button>
          )}
          {next ? (
            <Link
              className="btn"
              href={`/evals/${encodeURIComponent(run.runId)}/tasks/${encodeURIComponent(next.taskKey)}`}
            >
              #{next.taskId} →
            </Link>
          ) : (
            <button type="button" className="btn" disabled>
              next →
            </button>
          )}
        </div>
      </header>

      <section className="panel">
        <header className="panel-head">
          <h2>Episode {episode ? episode.index : "—"}</h2>
          {episode?.success == null ? (
            <span className="badge">unknown</span>
          ) : episode.success ? (
            <span className="badge badge-ok">success</span>
          ) : (
            <span className="badge badge-bad">fail</span>
          )}
        </header>
        {episode?.videoUrl ? (
          <video
            key={episode.videoUrl}
            className="task-video"
            src={episode.videoUrl}
            controls
            autoPlay
            muted
            playsInline
          />
        ) : (
          <p className="muted">このエピソードの動画はまだありません。</p>
        )}
        <div className="ep-strip">
          {task.episodes.map((ep) => (
            <button
              key={ep.index}
              type="button"
              className={`ep-chip${ep.index === episode?.index ? " ep-chip-on" : ""}`}
              onClick={() => setEpIndex(ep.index)}
            >
              {ep.index}
              {ep.success == null ? "" : ep.success ? " ✓" : " ✕"}
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
