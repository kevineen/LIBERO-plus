"use client";

import { useEffect, useRef } from "react";

import { fileUrl, useViewer } from "./store";

/** front / wrist カメラ映像をタイムラインに同期表示。 */
export default function CameraPanels() {
  const current = useViewer((s) => s.current);
  const frame = useViewer((s) => s.frame);
  const playing = useViewer((s) => s.playing);
  const fps = useViewer((s) => s.meta?.fps ?? 20);
  const frontUrl = current?.files.videos.front ? fileUrl(current.files.videos.front) : null;
  const wristUrl = current?.files.videos.wrist ? fileUrl(current.files.videos.wrist) : null;

  const frontRef = useRef<HTMLVideoElement>(null);
  const wristRef = useRef<HTMLVideoElement>(null);

  // 再生/停止の追随
  useEffect(() => {
    for (const v of [frontRef.current, wristRef.current]) {
      if (!v) continue;
      if (playing) {
        v.play().catch(() => undefined);
      } else {
        v.pause();
      }
    }
  }, [playing, frontUrl, wristUrl]);

  // フレーム → シーク（停止中は即座に、再生中はズレが大きい時のみ）
  useEffect(() => {
    const t = frame / Math.max(1, fps);
    for (const v of [frontRef.current, wristRef.current]) {
      if (!v) continue;
      if (playing) {
        if (Math.abs(v.currentTime - t) > 0.2) v.currentTime = t;
      } else {
        v.currentTime = t;
      }
    }
  }, [frame, fps, playing]);

  if (!frontUrl && !wristUrl) return null;

  return (
    <div className="pointer-events-none absolute right-2 top-2 flex flex-col gap-2">
      {frontUrl ? (
        <div className="overflow-hidden rounded border border-slate-700/80 bg-slate-950/70 shadow-lg">
          <div className="px-1.5 py-0.5 text-[10px] text-slate-400">front</div>
          <video
            ref={frontRef}
            src={frontUrl}
            muted
            playsInline
            preload="auto"
            className="block h-[90px] w-[90px] object-contain sm:h-[128px] sm:w-[128px]"
          />
        </div>
      ) : null}
      {wristUrl ? (
        <div className="overflow-hidden rounded border border-slate-700/80 bg-slate-950/70 shadow-lg">
          <div className="px-1.5 py-0.5 text-[10px] text-slate-400">wrist</div>
          <video
            ref={wristRef}
            src={wristUrl}
            muted
            playsInline
            preload="auto"
            className="block h-[90px] w-[90px] object-contain sm:h-[128px] sm:w-[128px]"
          />
        </div>
      ) : null}
    </div>
  );
}
