"use client";

import { useMemo, useState } from "react";

import { useViewer } from "./store";

/** エピソード一覧（検索・データセット/成否フィルタ付き）。 */
export default function EpisodeList() {
  const episodes = useViewer((s) => s.episodes);
  const currentId = useViewer((s) => s.current?.id ?? null);
  const selectEpisode = useViewer((s) => s.selectEpisode);
  const [query, setQuery] = useState("");
  const [dataset, setDataset] = useState("all");
  const [outcome, setOutcome] = useState("all");

  const datasets = useMemo(
    () => Array.from(new Set(episodes.map((e) => e.dataset).filter(Boolean))).sort(),
    [episodes],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return episodes.filter((e) => {
      if (dataset !== "all" && e.dataset !== dataset) return false;
      if (outcome === "success" && e.success !== true) return false;
      if (outcome === "fail" && e.success !== false) return false;
      if (q) {
        const hay = `${e.language} ${e.task} ${e.dataset} ${e.id}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [episodes, query, dataset, outcome]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <input
        className="rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-100 placeholder:text-slate-500 focus:border-sky-500 focus:outline-none"
        placeholder="検索（タスク / データセット）"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <div className="flex gap-2">
        <select
          className="min-w-0 flex-1 rounded border border-slate-700 bg-slate-800 px-1 py-1 text-xs text-slate-200"
          value={dataset}
          onChange={(e) => setDataset(e.target.value)}
        >
          <option value="all">全データセット</option>
          {datasets.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        <select
          className="rounded border border-slate-700 bg-slate-800 px-1 py-1 text-xs text-slate-200"
          value={outcome}
          onChange={(e) => setOutcome(e.target.value)}
        >
          <option value="all">全件</option>
          <option value="success">成功のみ</option>
          <option value="fail">失敗のみ</option>
        </select>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {filtered.length === 0 ? (
          <p className="px-1 py-4 text-xs text-slate-500">
            該当なし。parc-export-viewer で pack を生成してください。
          </p>
        ) : (
          <ul className="flex flex-col gap-1">
            {filtered.map((ep) => (
              <li key={ep.id}>
                <button
                  className={`w-full rounded px-2 py-2 text-left text-xs leading-snug ${
                    ep.id === currentId
                      ? "bg-sky-600/30 ring-1 ring-sky-500"
                      : "bg-slate-800/60 hover:bg-slate-700/70"
                  }`}
                  onClick={() => void selectEpisode(ep)}
                >
                  <div className="flex items-center gap-1">
                    <span
                      className={`inline-block h-2 w-2 shrink-0 rounded-full ${
                        ep.success === false ? "bg-rose-500" : "bg-emerald-500"
                      }`}
                      title={ep.success === false ? "失敗" : "成功"}
                    />
                    <span className="truncate text-slate-200">{ep.language || ep.task || ep.id}</span>
                  </div>
                  <div className="mt-0.5 flex gap-2 text-[10px] text-slate-500">
                    <span className="truncate">{ep.dataset}</span>
                    <span className="shrink-0">{ep.n_frames}f</span>
                    {ep.demo ? <span className="shrink-0">{ep.demo}</span> : null}
                    {ep.episode_index != null ? (
                      <span className="shrink-0">ep{ep.episode_index}</span>
                    ) : null}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
