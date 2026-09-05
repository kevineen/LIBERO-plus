"use client";

import { create } from "zustand";

export interface EpisodeEntry {
  id: string;
  dataset: string;
  task: string;
  language: string;
  episode_index: number | null;
  demo: string | null;
  n_frames: number;
  fps: number;
  success: boolean | null;
  replay_success: boolean | null;
  suite: string | null;
  task_id: number | null;
  generated: string | null;
  files: {
    meta: string;
    glb: string;
    tracks: string;
    videos: Record<string, string>;
  };
}

export interface PackBody {
  id: number;
  name: string;
  node: number;
}

export interface PackMeta {
  task: string;
  language: string;
  dataset: string;
  n_frames: number;
  n_bodies: number;
  fps: number;
  bodies: PackBody[];
  view: { min: number[]; max: number[]; center: number[]; radius: number };
  files: { videos: Record<string, string> };
}

export function fileUrl(rel: string): string {
  return `/api/v1/viewer/file?path=${encodeURIComponent(rel)}`;
}

interface ViewerState {
  episodes: EpisodeEntry[];
  indexError: string | null;
  current: EpisodeEntry | null;
  meta: PackMeta | null;
  frame: number;
  playing: boolean;
  speed: number;
  vrMenuOpen: boolean;
  sceneScale: number;
  loadIndex: () => Promise<void>;
  selectEpisode: (ep: EpisodeEntry) => Promise<void>;
  setFrame: (f: number) => void;
  stepFrame: (delta: number) => void;
  togglePlay: () => void;
  setSpeed: (s: number) => void;
  cycleSpeed: () => void;
  selectRelative: (delta: number) => void;
  setVrMenuOpen: (open: boolean) => void;
  multiplySceneScale: (factor: number) => void;
}

const SPEEDS = [0.25, 0.5, 1, 2];

export const useViewer = create<ViewerState>((set, get) => ({
  episodes: [],
  indexError: null,
  current: null,
  meta: null,
  frame: 0,
  playing: false,
  speed: 1,
  vrMenuOpen: false,
  sceneScale: 1,

  loadIndex: async () => {
    try {
      const res = await fetch("/api/v1/viewer/index");
      const data = await res.json();
      const episodes: EpisodeEntry[] = data.episodes ?? [];
      set({ episodes, indexError: null });
      if (episodes.length > 0 && !get().current) {
        await get().selectEpisode(episodes[0]);
      }
    } catch (err) {
      set({ indexError: String(err) });
    }
  },

  selectEpisode: async (ep) => {
    set({ current: ep, meta: null, frame: 0, playing: false });
    try {
      const res = await fetch(fileUrl(ep.files.meta));
      const meta: PackMeta = await res.json();
      set({ meta });
    } catch (err) {
      set({ indexError: String(err) });
    }
  },

  setFrame: (f) => {
    const { meta } = get();
    const max = Math.max(0, (meta?.n_frames ?? 1) - 1);
    set({ frame: Math.min(max, Math.max(0, Math.round(f))) });
  },

  stepFrame: (delta) => {
    const { frame } = get();
    get().setFrame(frame + delta);
  },

  togglePlay: () => {
    const { meta, playing } = get();
    if (!meta) return;
    if (!playing && get().frame >= meta.n_frames - 1) {
      set({ frame: 0 });
    }
    set({ playing: !playing });
  },

  setSpeed: (s) => set({ speed: s }),

  cycleSpeed: () => {
    const { speed } = get();
    const idx = SPEEDS.indexOf(speed);
    set({ speed: SPEEDS[(idx + 1) % SPEEDS.length] });
  },

  selectRelative: (delta) => {
    const { episodes, current } = get();
    if (!episodes.length) return;
    const idx = current ? episodes.findIndex((e) => e.id === current.id) : -1;
    const next = episodes[(idx + delta + episodes.length) % episodes.length];
    if (next) void get().selectEpisode(next);
  },

  setVrMenuOpen: (open) => set({ vrMenuOpen: open }),

  multiplySceneScale: (factor) => {
    const next = Math.min(6, Math.max(0.1, get().sceneScale * factor));
    set({ sceneScale: next });
  },
}));

export { SPEEDS };
