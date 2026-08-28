"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import type { EvalRunDetail, EvalRunSummary, EvalTask } from "@/lib/types";

type DocItem = { id: string; title: string; url: string };

type RouteCtx = {
  section: "evals" | "board" | "runs" | "jobs" | "docs" | "other";
  runId: string | null;
  suite: string | null;
  taskKey: string | null;
  docId: string | null;
  boardCol: string | null;
};

function parsePath(pathname: string): RouteCtx {
  const parts = pathname.split("/").filter(Boolean);
  if (parts[0] === "evals") {
    const runId = parts[1] ? decodeURIComponent(parts[1]) : null;
    let suite: string | null = null;
    let taskKey: string | null = null;
    if (parts[2] === "suites" && parts[3]) suite = decodeURIComponent(parts[3]);
    if (parts[2] === "tasks" && parts[3]) {
      taskKey = decodeURIComponent(parts[3]);
      const m = taskKey.match(/^(.+)_(\d+)$/);
      if (m) suite = m[1];
    }
    return { section: "evals", runId, suite, taskKey, docId: null, boardCol: null };
  }
  if (parts[0] === "board") {
    return { section: "board", runId: null, suite: null, taskKey: null, docId: null, boardCol: null };
  }
  if (parts[0] === "docs") {
    return {
      section: "docs",
      runId: null,
      suite: null,
      taskKey: null,
      docId: parts[1] ? decodeURIComponent(parts[1]) : null,
      boardCol: null,
    };
  }
  if (parts[0] === "runs") {
    return { section: "runs", runId: parts[1] ?? null, suite: null, taskKey: null, docId: null, boardCol: null };
  }
  if (pathname === "/" || pathname === "") {
    return { section: "runs", runId: null, suite: null, taskKey: null, docId: null, boardCol: null };
  }
  return { section: "other", runId: null, suite: null, taskKey: null, docId: null, boardCol: null };
}

function groupTasks(tasks: EvalTask[]): { suite: string; tasks: EvalTask[] }[] {
  const map = new Map<string, EvalTask[]>();
  for (const t of tasks) {
    const list = map.get(t.taskGroup) ?? [];
    list.push(t);
    map.set(t.taskGroup, list);
  }
  return [...map.entries()].map(([suite, list]) => ({
    suite,
    tasks: list.sort((a, b) => a.taskId - b.taskId),
  }));
}

function suitesOf(detail: EvalRunDetail | undefined): { suite: string; tasks: EvalTask[] }[] {
  if (!detail) return [];
  const grouped = groupTasks(detail.tasks);
  if (grouped.length > 0) return grouped;
  return detail.groups.map((g) => ({ suite: g.taskGroup, tasks: [] }));
}

function fmtRate(rate: number | null): string {
  if (rate == null) return "";
  return `${Math.round(rate * 100)}%`;
}

type Props = {
  open: boolean;
  onClose: () => void;
};

/**
 * アプリ全体の階層ナビ。
 * Evals → run → suite → task をサイドバーから辿れる。
 */
export function AppSidebar({ open, onClose }: Props) {
  const pathname = usePathname();
  const ctx = useMemo(() => parsePath(pathname), [pathname]);

  const [evalRuns, setEvalRuns] = useState<EvalRunSummary[]>([]);
  const [details, setDetails] = useState<Record<string, EvalRunDetail>>({});
  const [docs, setDocs] = useState<DocItem[]>([]);
  const [openEvals, setOpenEvals] = useState(true);
  const [openBoard, setOpenBoard] = useState(false);
  const [openDocs, setOpenDocs] = useState(false);
  const [expandedRuns, setExpandedRuns] = useState<Set<string>>(new Set());
  const [expandedSuites, setExpandedSuites] = useState<Set<string>>(new Set());

  const loadEvals = useCallback(async () => {
    try {
      const data = (await (await fetch("/api/v1/evals", { cache: "no-store" })).json()) as {
        runs: EvalRunSummary[];
      };
      setEvalRuns(data.runs ?? []);
    } catch {
      /* サイドバーは失敗しても本体を止めない */
    }
  }, []);

  const loadDetail = useCallback(async (runId: string) => {
    try {
      const data = (await (
        await fetch(`/api/v1/evals/${encodeURIComponent(runId)}`, { cache: "no-store" })
      ).json()) as { run: EvalRunDetail };
      if (data.run) {
        setDetails((prev) => ({ ...prev, [runId]: data.run }));
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    void loadEvals();
    void fetch("/api/v1/docs")
      .then((r) => r.json())
      .then((d) => setDocs((d.docs ?? []) as DocItem[]))
      .catch(() => undefined);
  }, [loadEvals]);

  // URL に合わせて枝を開く
  useEffect(() => {
    if (ctx.section === "evals") setOpenEvals(true);
    if (ctx.section === "board") setOpenBoard(true);
    if (ctx.section === "docs") setOpenDocs(true);
    if (ctx.runId) {
      setExpandedRuns((prev) => new Set(prev).add(ctx.runId!));
      void loadDetail(ctx.runId);
    }
    if (ctx.runId && ctx.suite) {
      const key = `${ctx.runId}:${ctx.suite}`;
      setExpandedSuites((prev) => new Set(prev).add(key));
    }
  }, [ctx, loadDetail]);

  // 展開中の run 詳細と一覧をポーリング
  useEffect(() => {
    const id = window.setInterval(() => {
      void loadEvals();
      for (const runId of expandedRuns) {
        void loadDetail(runId);
      }
    }, 5000);
    return () => window.clearInterval(id);
  }, [loadEvals, loadDetail, expandedRuns]);

  function toggleRun(runId: string) {
    setExpandedRuns((prev) => {
      const next = new Set(prev);
      if (next.has(runId)) next.delete(runId);
      else {
        next.add(runId);
        void loadDetail(runId);
      }
      return next;
    });
  }

  function toggleSuite(runId: string, suite: string) {
    const key = `${runId}:${suite}`;
    setExpandedSuites((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <aside className={`app-sidebar${open ? " is-open" : ""}`}>
      <div className="sidebar-brand">
        <Link href="/evals" className="brand" onClick={onClose}>
          PARC Lab
        </Link>
        <button type="button" className="sidebar-close" onClick={onClose} aria-label="閉じる">
          ×
        </button>
      </div>

      <nav className="sidebar-tree" aria-label="階層ナビ">
        <TreeSection
          label="Evals"
          href="/evals"
          active={ctx.section === "evals" && !ctx.runId}
          open={openEvals}
          onToggle={() => setOpenEvals((v) => !v)}
          onNavigate={onClose}
          badge={evalRuns.filter((r) => r.status === "running").length || undefined}
        >
          {evalRuns.map((r) => {
            const detail = details[r.runId];
            const suiteList = suitesOf(detail);
            const runOpen = expandedRuns.has(r.runId);
            return (
              <TreeItem
                key={r.runId}
                href={`/evals/${encodeURIComponent(r.runId)}`}
                label={r.runId}
                meta={
                  r.status === "running"
                    ? "run"
                    : fmtRate(r.successRate) || (r.status === "finished" ? "done" : undefined)
                }
                tone={r.status === "running" ? "run" : r.status === "finished" ? "ok" : undefined}
                active={ctx.runId === r.runId && !ctx.suite && !ctx.taskKey}
                expandable
                open={runOpen}
                onToggle={() => toggleRun(r.runId)}
                onNavigate={onClose}
              >
                {runOpen && !detail ? (
                  <div className="tree-leaf muted">読み込み中…</div>
                ) : runOpen && suiteList.length === 0 ? (
                  <div className="tree-leaf muted">タスクなし</div>
                ) : runOpen ? (
                  suiteList.map((s) => {
                    const suiteKey = `${r.runId}:${s.suite}`;
                    const suiteOpen = expandedSuites.has(suiteKey);
                    return (
                      <TreeItem
                        key={s.suite}
                        href={`/evals/${encodeURIComponent(r.runId)}/suites/${encodeURIComponent(s.suite)}`}
                        label={s.suite}
                        meta={s.tasks.length ? String(s.tasks.length) : undefined}
                        active={ctx.runId === r.runId && ctx.suite === s.suite && !ctx.taskKey}
                        expandable={s.tasks.length > 0}
                        open={suiteOpen}
                        onToggle={() => toggleSuite(r.runId, s.suite)}
                        onNavigate={onClose}
                      >
                        {suiteOpen
                          ? s.tasks.map((t) => (
                              <TreeItem
                                key={t.taskKey}
                                href={`/evals/${encodeURIComponent(r.runId)}/tasks/${encodeURIComponent(t.taskKey)}`}
                                label={`#${t.taskId}`}
                                meta={
                                  t.successRate == null
                                    ? `${t.nEpisodes}ep`
                                    : `${t.nSuccess}/${t.nEpisodes}`
                                }
                                tone={
                                  t.successRate == null
                                    ? undefined
                                    : t.successRate >= 1
                                      ? "ok"
                                      : t.successRate === 0
                                        ? "bad"
                                        : undefined
                                }
                                active={ctx.taskKey === t.taskKey}
                                onNavigate={onClose}
                              />
                            ))
                          : null}
                      </TreeItem>
                    );
                  })
                ) : null}
              </TreeItem>
            );
          })}
        </TreeSection>

        <TreeSection
          label="Board"
          href="/board"
          active={ctx.section === "board"}
          open={openBoard}
          onToggle={() => setOpenBoard((v) => !v)}
          onNavigate={onClose}
        >
          <TreeItem href="/board#col-todo" label="未着手" onNavigate={onClose} />
          <TreeItem href="/board#col-doing" label="進行中" onNavigate={onClose} />
          <TreeItem href="/board#col-done" label="完了" onNavigate={onClose} />
        </TreeSection>

        <TreeSection
          label="Runs"
          href="/"
          active={ctx.section === "runs"}
          open={false}
          onToggle={() => undefined}
          onNavigate={onClose}
          leaf
        />

        <TreeSection
          label="Jobs"
          href="/#jobs"
          active={false}
          open={false}
          onToggle={() => undefined}
          onNavigate={onClose}
          leaf
        />

        <TreeSection
          label="Docs"
          href="/docs"
          active={ctx.section === "docs" && !ctx.docId}
          open={openDocs}
          onToggle={() => setOpenDocs((v) => !v)}
          onNavigate={onClose}
        >
          {docs.map((d) => (
            <TreeItem
              key={d.id}
              href={d.url}
              label={d.title}
              active={ctx.docId === d.id}
              onNavigate={onClose}
            />
          ))}
        </TreeSection>
      </nav>
    </aside>
  );
}

function TreeSection({
  label,
  href,
  active,
  open,
  onToggle,
  onNavigate,
  children,
  badge,
  leaf,
}: {
  label: string;
  href: string;
  active: boolean;
  open: boolean;
  onToggle: () => void;
  onNavigate: () => void;
  children?: ReactNode;
  badge?: number;
  leaf?: boolean;
}) {
  return (
    <div className="tree-section">
      <div className={`tree-row${active ? " is-active" : ""}`}>
        {leaf ? (
          <span className="tree-chevron tree-chevron-spacer" />
        ) : (
          <button type="button" className="tree-chevron" onClick={onToggle} aria-label="開閉">
            {open ? "▾" : "▸"}
          </button>
        )}
        <Link href={href} className="tree-link" onClick={onNavigate}>
          {label}
          {badge ? <span className="tree-badge">{badge}</span> : null}
        </Link>
      </div>
      {!leaf && open ? <div className="tree-children">{children}</div> : null}
    </div>
  );
}

function TreeItem({
  href,
  label,
  meta,
  tone,
  active,
  expandable,
  open,
  onToggle,
  onNavigate,
  children,
}: {
  href: string;
  label: string;
  meta?: string;
  tone?: "run" | "ok" | "bad";
  active?: boolean;
  expandable?: boolean;
  open?: boolean;
  onToggle?: () => void;
  onNavigate: () => void;
  children?: ReactNode;
}) {
  return (
    <div className="tree-item">
      <div className={`tree-row${active ? " is-active" : ""}`}>
        {expandable ? (
          <button type="button" className="tree-chevron" onClick={onToggle} aria-label="開閉">
            {open ? "▾" : "▸"}
          </button>
        ) : (
          <span className="tree-chevron tree-chevron-spacer" />
        )}
        <Link href={href} className="tree-link" onClick={onNavigate} title={label}>
          <span className="tree-label">{label}</span>
          {meta ? <span className={`tree-meta${tone ? ` tone-${tone}` : ""}`}>{meta}</span> : null}
        </Link>
      </div>
      {expandable && open ? <div className="tree-children">{children}</div> : null}
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  return (
    <div className="app-shell">
      <button type="button" className="sidebar-toggle" onClick={() => setOpen(true)}>
        メニュー
      </button>
      {open ? <div className="sidebar-backdrop" onClick={() => setOpen(false)} /> : null}
      <AppSidebar open={open} onClose={() => setOpen(false)} />
      <main className="app-main">{children}</main>
    </div>
  );
}
