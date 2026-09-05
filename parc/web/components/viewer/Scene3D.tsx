"use client";

import { useEffect, useMemo, useRef } from "react";

import { useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, useGLTF } from "@react-three/drei";
import { useXR } from "@react-three/xr";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import * as THREE from "three";

import { fileUrl, useViewer, type EpisodeEntry, type PackMeta } from "./store";

/** GLB + トラック適用。再生進行はここで回す。 */
function SceneModel({ episode, meta }: { episode: EpisodeEntry; meta: PackMeta }) {
  const gltf = useGLTF(fileUrl(episode.files.glb));
  const tracksRef = useRef<Float32Array | null>(null);
  const accRef = useRef(0);
  const lastAppliedRef = useRef(-1);

  useEffect(() => {
    let cancelled = false;
    tracksRef.current = null;
    const tracksUrl = fileUrl(episode.files.tracks);
    fetch(tracksUrl)
      .then((res) => res.arrayBuffer())
      .then((buf) => {
        if (!cancelled) tracksRef.current = new Float32Array(buf);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
      // GLB の suspense キャッシュを解放（5MB/エピソード程度あるため）
      useGLTF.clear(fileUrl(episode.files.glb));
    };
  }, [episode.id, episode.files.tracks, episode.files.glb]);

  // glTF ノード index → Object3D（GLTFLoader の associations から逆引き）
  const nodeMap = useMemo(() => {
    const m = new Map<number, THREE.Object3D>();
    const assoc = (gltf as { parser?: { associations?: Map<THREE.Object3D, { nodes?: number }> } })
      .parser?.associations;
    if (assoc) {
      for (const [obj, a] of assoc) {
        if (a && typeof a.nodes === "number") m.set(a.nodes, obj);
      }
    }
    return m;
  }, [gltf]);

  useFrame((_, delta) => {
    const tracks = tracksRef.current;
    if (!tracks) return;
    const state = useViewer.getState();
    const m = state.meta;
    if (!m) return;
    const lastFrame = m.n_frames - 1;

    // 再生進行（フレーム消費）
    if (state.playing) {
      accRef.current += delta * m.fps * state.speed;
      const advance = Math.floor(accRef.current);
      if (advance > 0) {
        accRef.current -= advance;
        const next = state.frame + advance;
        if (next >= lastFrame) {
          useViewer.setState({ frame: lastFrame, playing: false });
        } else {
          useViewer.setState({ frame: next });
        }
      }
    } else {
      accRef.current = 0;
    }

    const frame = useViewer.getState().frame;
    if (frame === lastAppliedRef.current && !state.playing) return;
    lastAppliedRef.current = frame;

    const base = frame * m.n_bodies * 7;
    for (const body of meta.bodies) {
      const node = body.node >= 0 ? nodeMap.get(body.node) : undefined;
      if (!node) continue;
      const o = base + body.id * 7;
      node.position.set(tracks[o], tracks[o + 1], tracks[o + 2]);
      // MuJoCo (w,x,y,z) → three (x,y,z,w)
      node.quaternion.set(tracks[o + 4], tracks[o + 5], tracks[o + 6], tracks[o + 3]);
    }
  });

  return <primitive object={gltf.scene} />;
}

/** カメラ・OrbitControls の初期化（シーン範囲から視点を決める）。 */
function CameraRig({ meta }: { meta: PackMeta | null }) {
  const camera = useThree((s) => s.camera);
  const controlsRef = useRef<OrbitControlsImpl | null>(null);

  const cam = useMemo(() => {
    const center = meta?.view?.center ?? [0, 0.8, 0];
    const radius = Math.max(0.5, meta?.view?.radius ?? 1.0);
    return {
      target: new THREE.Vector3(center[0], center[1], center[2]),
      position: new THREE.Vector3(
        center[0] + radius * 1.4,
        center[1] + radius * 1.3,
        center[2] + radius * 2.0,
      ),
    };
  }, [meta]);

  useEffect(() => {
    camera.position.copy(cam.position);
    camera.lookAt(cam.target);
    const c = controlsRef.current;
    if (c) {
      c.target.copy(cam.target);
      c.update();
    }
  }, [camera, cam]);

  return (
    <OrbitControls ref={controlsRef} target={cam.target} minDistance={0.3} maxDistance={10} />
  );
}

export default function Scene3D() {
  const current = useViewer((s) => s.current);
  const meta = useViewer((s) => s.meta);
  const sceneScale = useViewer((s) => s.sceneScale);
  const inXR = useXR((s) => s.session != null);

  return (
    <>
      <ambientLight intensity={1.1} />
      <directionalLight position={[2, 4, 2]} intensity={1.6} />
      <directionalLight position={[-2, 3, -2]} intensity={0.6} color="#cdd7ff" />
      <group scale={sceneScale}>
        {current && meta ? <SceneModel key={current.id} episode={current} meta={meta} /> : null}
      </group>
      {!inXR ? <CameraRig meta={meta} /> : null}
    </>
  );
}
