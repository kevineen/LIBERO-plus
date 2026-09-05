"use client";

import { SPEEDS, useViewer } from "./store";

/** 再生コントロール（タッチでも扱いやすい大きめ UI）。 */
export default function PlaybackBar() {
  const frame = useViewer((s) => s.frame);
  const playing = useViewer((s) => s.playing);
  const speed = useViewer((s) => s.speed);
  const meta = useViewer((s) => s.meta);
  const current = useViewer((s) => s.current);
  const togglePlay = useViewer((s) => s.togglePlay);
  const setFrame = useViewer((s) => s.setFrame);
  const stepFrame = useViewer((s) => s.stepFrame);
  const cycleSpeed = useViewer((s) => s.cycleSpeed);
  const setSpeed = useViewer((s) => s.setSpeed);
  const selectRelative = useViewer((s) => s.selectRelative);

  const nFrames = meta?.n_frames ?? 0;
  const disabled = !meta;

  return (
    <div className="border-t border-slate-800 bg-slate-900/90 px-3 py-2 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-col gap-2">
        <div className="flex items-center gap-2">
          <button
            className="rounded bg-slate-800 px-3 py-2 text-sm text-slate-200 hover:bg-slate-700 disabled:opacity-40"
            disabled={disabled}
            onClick={() => selectRelative(-1)}
            title="前のエピソード"
          >
            ⏮
          </button>
          <button
            className="rounded bg-slate-800 px-3 py-2 text-sm text-slate-200 hover:bg-slate-700 disabled:opacity-40"
            disabled={disabled}
            onClick={() => stepFrame(-10)}
          >
            −10
          </button>
          <button
            className="rounded bg-sky-600 px-5 py-2 text-base font-semibold text-white hover:bg-sky-500 disabled:opacity-40"
            disabled={disabled}
            onClick={togglePlay}
          >
            {playing ? "⏸ 一時停止" : "▶ 再生"}
          </button>
          <button
            className="rounded bg-slate-800 px-3 py-2 text-sm text-slate-200 hover:bg-slate-700 disabled:opacity-40"
            disabled={disabled}
            onClick={() => stepFrame(10)}
          >
            +10
          </button>
          <button
            className="rounded bg-slate-800 px-3 py-2 text-sm text-slate-200 hover:bg-slate-700 disabled:opacity-40"
            disabled={disabled}
            onClick={() => selectRelative(1)}
            title="次のエピソード"
          >
            ⏭
          </button>

          <div className="ml-2 hidden items-center gap-1 sm:flex">
            {SPEEDS.map((s) => (
              <button
                key={s}
                className={`rounded px-2 py-1 text-xs ${
                  speed === s
                    ? "bg-sky-600 text-white"
                    : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                }`}
                onClick={() => setSpeed(s)}
              >
                {s}x
              </button>
            ))}
          </div>
          <button
            className="rounded bg-slate-800 px-2 py-1 text-xs text-slate-300 hover:bg-slate-700 sm:hidden"
            onClick={cycleSpeed}
          >
            {speed}x
          </button>

          <div className="ml-auto text-right text-xs text-slate-400">
            <div className="max-w-[280px] truncate sm:max-w-md" title={current?.language}>
              {current?.language || current?.task || "—"}
            </div>
            <div>
              フレーム {nFrames ? frame + 1 : 0} / {nFrames}（{meta?.fps ?? "-"}fps）
            </div>
          </div>
        </div>

        <input
          type="range"
          min={0}
          max={Math.max(0, nFrames - 1)}
          value={frame}
          disabled={disabled}
          onChange={(e) => setFrame(Number(e.target.value))}
          className="h-6 w-full cursor-pointer accent-sky-500"
          aria-label="タイムライン"
        />
      </div>
    </div>
  );
}
