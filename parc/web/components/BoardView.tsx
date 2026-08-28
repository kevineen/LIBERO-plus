"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import type { BoardCard, BoardColumn, EvalRunSummary } from "@/lib/types";

const COLUMNS: { id: BoardColumn; label: string }[] = [
  { id: "todo", label: "未着手" },
  { id: "doing", label: "進行中" },
  { id: "done", label: "完了" },
];

const NEXT_STATUS: Record<BoardColumn, BoardColumn | null> = {
  todo: "doing",
  doing: "done",
  done: null,
};

const PREV_STATUS: Record<BoardColumn, BoardColumn | null> = {
  todo: null,
  doing: "todo",
  done: "doing",
};

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: "no-store", ...init });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { error?: string };
    throw new Error(body.error || `${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export function BoardView() {
  const [cards, setCards] = useState<BoardCard[]>([]);
  const [evals, setEvals] = useState<EvalRunSummary[]>([]);
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [evalRunId, setEvalRunId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [board, evalsRes] = await Promise.all([
        fetchJson<{ cards: BoardCard[] }>("/api/v1/board"),
        fetchJson<{ runs: EvalRunSummary[] }>("/api/v1/evals"),
      ]);
      setCards(board.cards);
      setEvals(evalsRes.runs);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load board");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const grouped = useMemo(() => {
    const map: Record<BoardColumn, BoardCard[]> = { todo: [], doing: [], done: [] };
    for (const c of cards) map[c.status].push(c);
    return map;
  }, [cards]);

  async function addCard(e: FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    try {
      await fetchJson("/api/v1/board", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          notes: notes.trim(),
          evalRunId: evalRunId || null,
        }),
      });
      setTitle("");
      setNotes("");
      setEvalRunId("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "create failed");
    } finally {
      setBusy(false);
    }
  }

  async function move(card: BoardCard, status: BoardColumn) {
    setBusy(true);
    try {
      await fetchJson(`/api/v1/board/${encodeURIComponent(card.id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "update failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove(card: BoardCard) {
    setBusy(true);
    try {
      await fetchJson(`/api/v1/board/${encodeURIComponent(card.id)}`, {
        method: "DELETE",
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "delete failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <section className="hero-band">
        <div>
          <p className="eyebrow">LIBERO-plus · research board</p>
          <h1>Board</h1>
          <p className="lede">研究作業を未着手 / 進行中 / 完了で管理します。評価 run へのリンクも付けられます。</p>
        </div>
        <div className="stat-pills">
          <div>
            <span className="stat-n">{grouped.todo.length}</span>
            <span className="muted">未着手</span>
          </div>
          <div>
            <span className="stat-n">{grouped.doing.length}</span>
            <span className="muted">進行中</span>
          </div>
          <div>
            <span className="stat-n">{grouped.done.length}</span>
            <span className="muted">完了</span>
          </div>
        </div>
      </section>

      {error ? <p className="error">{error}</p> : null}

      <form className="panel board-form" onSubmit={addCard}>
        <header className="panel-head">
          <h2>カードを追加</h2>
        </header>
        <div className="toolbar wrap">
          <input
            className="input grow"
            placeholder="タイトル"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
          />
          <select
            className="input"
            value={evalRunId}
            onChange={(e) => setEvalRunId(e.target.value)}
          >
            <option value="">評価 run（任意）</option>
            {evals.map((r) => (
              <option key={r.runId} value={r.runId}>
                {r.runId}
              </option>
            ))}
          </select>
          <button className="btn" type="submit" disabled={busy || !title.trim()}>
            追加
          </button>
        </div>
        <textarea
          className="input board-notes"
          placeholder="メモ（任意）"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
        />
      </form>

      <div className="board-cols">
        {COLUMNS.map((col) => (
          <section key={col.id} id={`col-${col.id}`} className="panel board-col">
            <header className="panel-head">
              <h2>{col.label}</h2>
              <span className="muted mono">{grouped[col.id].length}</span>
            </header>
            <ul className="board-list">
              {grouped[col.id].length === 0 ? (
                <li className="muted">カードなし</li>
              ) : (
                grouped[col.id].map((card) => {
                  const prev = PREV_STATUS[card.status];
                  const next = NEXT_STATUS[card.status];
                  return (
                    <li key={card.id} className="board-card">
                      <strong>{card.title}</strong>
                      {card.notes ? <p className="board-card-notes">{card.notes}</p> : null}
                      {card.evalRunId ? (
                        <Link
                          className="mono small"
                          href={`/evals/${encodeURIComponent(card.evalRunId)}`}
                        >
                          eval: {card.evalRunId}
                        </Link>
                      ) : null}
                      <div className="row-actions">
                        {prev ? (
                          <button
                            type="button"
                            className="btn btn-ghost btn-tiny"
                            disabled={busy}
                            onClick={() => void move(card, prev)}
                          >
                            ← {COLUMNS.find((c) => c.id === prev)?.label}
                          </button>
                        ) : null}
                        {next ? (
                          <button
                            type="button"
                            className="btn btn-tiny"
                            disabled={busy}
                            onClick={() => void move(card, next)}
                          >
                            {COLUMNS.find((c) => c.id === next)?.label} →
                          </button>
                        ) : null}
                        <button
                          type="button"
                          className="btn btn-ghost btn-tiny"
                          disabled={busy}
                          onClick={() => void remove(card)}
                        >
                          削除
                        </button>
                      </div>
                    </li>
                  );
                })
              )}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
