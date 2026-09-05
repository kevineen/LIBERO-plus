"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";

import { createXRStore, XR } from "@react-three/xr";

import { useViewer } from "./store";
import EpisodeList from "./EpisodeList";
import PlaybackBar from "./PlaybackBar";
import CameraPanels from "./CameraPanels";

const Canvas = dynamic(() => import("@react-three/fiber").then((m) => m.Canvas), {
  ssr: false,
});
const Scene3D = dynamic(() => import("./Scene3D"), { ssr: false });
const VrLayer = dynamic(() => import("./VrLayer"), { ssr: false });

const xrStore = createXRStore();

function EnterVrButton() {
  const [supported, setSupported] = useState(false);
  useEffect(() => {
    const xr = (navigator as Navigator & { xr?: { isSessionSupported(m: string): Promise<boolean> } })
      .xr;
    if (xr) {
      xr.isSessionSupported("immersive-vr").then(setSupported).catch(() => setSupported(false));
    }
  }, []);
  if (!supported) return null;
  return (
    <button
      className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-emerald-500"
      onClick={() => void xrStore.enterVR()}
    >
      Enter VR
    </button>
  );
}

export default function ViewerClient() {
  const loadIndex = useViewer((s) => s.loadIndex);
  const indexError = useViewer((s) => s.indexError);
  const episodes = useViewer((s) => s.episodes);
  const current = useViewer((s) => s.current);
  const togglePlay = useViewer((s) => s.togglePlay);
  const stepFrame = useViewer((s) => s.stepFrame);
  const selectRelative = useViewer((s) => s.selectRelative);
  const [listOpen, setListOpen] = useState(true);

  useEffect(() => {
    void loadIndex();
  }, [loadIndex]);

  // キーボードショートカット
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      if (e.code === "Space") {
        e.preventDefault();
        togglePlay();
      } else if (e.key === "ArrowLeft") {
        stepFrame(-1);
      } else if (e.key === "ArrowRight") {
        stepFrame(1);
      } else if (e.key === "ArrowUp") {
        selectRelative(-1);
      } else if (e.key === "ArrowDown") {
        selectRelative(1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [togglePlay, stepFrame, selectRelative]);

  return (
    <div className="flex h-dvh flex-col bg-slate-950 text-slate-100">
      <header className="flex items-center gap-2 border-b border-slate-800 bg-slate-900/90 px-3 py-2">
        <Link href="/" className="text-sm font-semibold text-sky-400 hover:underline">
          parc
        </Link>
        <span className="text-sm font-semibold">Episode Viewer</span>
        <span className="text-xs text-slate-500">
          {episodes.length > 0 ? `${episodes.length} エピソード` : indexError ? "index 取得失敗" : "…"}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <button
            className="rounded bg-slate-800 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-700 lg:hidden"
            onClick={() => setListOpen((v) => !v)}
          >
            リスト
          </button>
          <EnterVrButton />
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside
          className={`${
            listOpen ? "flex" : "hidden"
          } w-64 shrink-0 flex-col gap-2 border-r border-slate-800 bg-slate-900/60 p-2 lg:flex`}
        >
          <EpisodeList />
        </aside>

        <main className="relative min-h-0 flex-1">
          <Canvas
            camera={{ position: [1.4, 2.1, 2.0], fov: 50, near: 0.05, far: 50 }}
            dpr={[1, 2]}
            gl={{ antialias: true }}
          >
            <XR store={xrStore}>
              <Scene3D />
              <VrLayer />
            </XR>
          </Canvas>
          <CameraPanels />
          {!current ? (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              <p className="rounded bg-slate-900/80 px-4 py-3 text-sm text-slate-300">
                {episodes.length === 0 && !indexError
                  ? "pack がありません。parc-export-viewer で生成してください。"
                  : "読み込み中…"}
              </p>
            </div>
          ) : null}
        </main>
      </div>

      <PlaybackBar />
    </div>
  );
}
