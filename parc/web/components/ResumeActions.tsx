"use client";

import { useState } from "react";

/** Run 詳細から resume / eval をキューへ */
export function ResumeActions({ runId }: { runId: string }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Resume / 再評価</h2>
        <span className="muted">ckpt があれば eval、学習継続は train</span>
      </header>
      <div className="toolbar">
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
      </div>
      {error ? <p className="error">{error}</p> : null}
      {msg ? <p className="muted mono small">{msg}</p> : null}
    </section>
  );
}
