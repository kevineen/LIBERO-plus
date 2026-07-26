"use client";

import { useCallback, useEffect, useState } from "react";

type Props = {
  runId: string;
  /** meta.status — running 中は Pause、それ以外は Resume */
  runStatus?: string;
};

type QueueJob = {
  job_id: string;
  status: string;
  run_id?: string | null;
};

/** Run 詳細から Pause / resume / eval をキューへ */
export function ResumeActions({ runId, runStatus = "" }: Props) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [linkedJobId, setLinkedJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);

  const refreshLink = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/queue?limit=80");
      if (!res.ok) return;
      const data = (await res.json()) as { jobs?: QueueJob[] };
      const jobs = data.jobs ?? [];
      const linked = jobs.find((j) => j.run_id === runId);
      setLinkedJobId(linked?.job_id ?? null);
      setJobStatus(linked?.status ?? null);
    } catch {
      /* ignore */
    }
  }, [runId]);

  useEffect(() => {
    void refreshLink();
    const t = window.setInterval(() => void refreshLink(), 8000);
    return () => window.clearInterval(t);
  }, [refreshLink]);

  const isRunning =
    runStatus === "running" || jobStatus === "running" || jobStatus === "queued";

  async function pause() {
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      let jobId = linkedJobId;
      if (!jobId) {
        await refreshLink();
        const res = await fetch("/api/v1/queue?limit=80");
        const data = (await res.json()) as { jobs?: QueueJob[] };
        jobId =
          data.jobs?.find(
            (j) => j.run_id === runId && (j.status === "running" || j.status === "queued"),
          )?.job_id ?? null;
      }
      if (!jobId) {
        throw new Error("この run に紐づく running/queued ジョブが見つかりません");
      }
      const res = await fetch("/api/v1/queue", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "pause", jobId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? res.statusText);
      setMsg(`Paused job ${jobId.slice(0, 22)}… — 再開は Resume (train)`);
      await refreshLink();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function resume(mode: "auto" | "eval" | "train") {
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const res = await fetch("/api/v1/queue", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "resume", runId, mode }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? res.statusText);
      setMsg(`queued: ${JSON.stringify(data.result ?? data).slice(0, 200)}`);
      await refreshLink();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>{isRunning ? "Pause（GPU 解放）" : "Resume / 再評価"}</h2>
        <span className="muted">
          {isRunning
            ? "学習/評価プロセスを止め、あとで Resume から再開"
            : "ckpt があれば eval、学習継続は train"}
        </span>
      </header>
      <div className="toolbar">
        {isRunning ? (
          <button
            type="button"
            className="btn"
            disabled={busy}
            onClick={() => void pause()}
            title="Stop process and free GPU"
          >
            Pause
          </button>
        ) : (
          <>
            <button
              type="button"
              className="btn"
              disabled={busy}
              onClick={() => void resume("auto")}
            >
              Resume (auto)
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={busy}
              onClick={() => void resume("eval")}
            >
              Eval only
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={busy}
              onClick={() => void resume("train")}
            >
              Train continue
            </button>
          </>
        )}
      </div>
      {error ? <p className="error">{error}</p> : null}
      {msg ? <p className="muted mono small">{msg}</p> : null}
    </section>
  );
}
