"use client";

import { useMemo, useRef, useState } from "react";

import { useFrame } from "@react-three/fiber";
import { Text } from "@react-three/drei";
import {
  useXR,
  useXRControllerButtonEvent,
  useXRControllerLocomotion,
  useXRInputSourceState,
  XROrigin,
} from "@react-three/xr";
import * as THREE from "three";

import { useViewer } from "./store";

/** VR 内 ボタン（plane + text、pointer events でクリック）。 */
function VrButton({
  label,
  width = 0.14,
  height = 0.06,
  fontSize = 0.032,
  primary = false,
  onClick,
}: {
  label: string;
  width?: number;
  height?: number;
  fontSize?: number;
  primary?: boolean;
  onClick: () => void;
}) {
  const [hover, setHover] = useState(false);
  const color = hover ? "#2563eb" : primary ? "#1d4ed8" : "#1e293b";
  return (
    <group>
      <mesh
        onPointerOver={() => setHover(true)}
        onPointerOut={() => setHover(false)}
        onClick={(e) => {
          e.stopPropagation();
          onClick();
        }}
      >
        <boxGeometry args={[width, height, 0.008]} />
        <meshStandardMaterial color={color} roughness={0.6} />
      </mesh>
      <Text
        position={[0, 0, 0.006]}
        fontSize={fontSize}
        color="#f8fafc"
        anchorX="center"
        anchorY="middle"
        maxWidth={width * 1.8}
      >
        {label}
      </Text>
    </group>
  );
}

/** VR 内タイムライン（クリック位置でシーク）。 */
function VrTimeline({ width = 1.0 }: { width?: number }) {
  const frame = useViewer((s) => s.frame);
  const meta = useViewer((s) => s.meta);
  const setFrame = useViewer((s) => s.setFrame);
  const nFrames = meta?.n_frames ?? 1;
  const frac = nFrames > 1 ? frame / (nFrames - 1) : 0;

  return (
    <group>
      <mesh
        onPointerDown={(e) => {
          e.stopPropagation();
          if (e.uv && nFrames > 1) {
            setFrame(Math.round(e.uv.x * (nFrames - 1)));
          }
        }}
      >
        <planeGeometry args={[width, 0.05]} />
        <meshStandardMaterial color="#0f172a" roughness={0.8} />
      </mesh>
      {/* 進行バー */}
      <mesh position={[-width / 2 + (width * frac) / 2, 0, 0.002]}>
        <planeGeometry args={[Math.max(0.004, width * frac), 0.03]} />
        <meshStandardMaterial color="#38bdf8" emissive="#0ea5e9" emissiveIntensity={0.6} />
      </mesh>
      <Text position={[0, 0.05, 0]} fontSize={0.026} color="#cbd5e1" anchorY="bottom">
        {`${frame + 1} / ${nFrames}`}
      </Text>
    </group>
  );
}

/** 再生コントロールパネル（プレイヤー前方に固定）。 */
function PlaybackPanel() {
  const playing = useViewer((s) => s.playing);
  const speed = useViewer((s) => s.speed);
  const task = useViewer((s) => s.current?.task ?? "");
  const togglePlay = useViewer((s) => s.togglePlay);
  const cycleSpeed = useViewer((s) => s.cycleSpeed);
  const stepFrame = useViewer((s) => s.stepFrame);
  const selectRelative = useViewer((s) => s.selectRelative);

  return (
    <group position={[0, 1.15, -0.75]} rotation={[-0.35, 0, 0]}>
      {/* 背景 */}
      <mesh position={[0, 0, -0.01]}>
        <planeGeometry args={[1.5, 0.44]} />
        <meshStandardMaterial color="#020617" transparent opacity={0.82} roughness={0.9} />
      </mesh>
      <Text position={[-0.7, 0.15, 0]} fontSize={0.034} color="#e2e8f0" anchorX="left">
        {task.slice(0, 46)}
      </Text>
      <group position={[-0.42, 0.0, 0]}>
        <VrButton label="|<" width={0.11} height={0.075} onClick={() => selectRelative(-1)} />
        <group position={[0.15, 0, 0]}>
          <VrButton label="-10" width={0.11} height={0.075} onClick={() => stepFrame(-10)} />
        </group>
        <group position={[0.3, 0, 0]}>
          <VrButton
            label={playing ? "II" : ">"}
            width={0.11}
            height={0.075}
            primary
            onClick={togglePlay}
          />
        </group>
        <group position={[0.45, 0, 0]}>
          <VrButton label="+10" width={0.11} height={0.075} onClick={() => stepFrame(10)} />
        </group>
        <group position={[0.6, 0, 0]}>
          <VrButton label=">|" width={0.11} height={0.075} onClick={() => selectRelative(1)} />
        </group>
      </group>
      <group position={[-0.16, 0.0, 0]}>
        <VrTimeline width={0.95} />
      </group>
      <group position={[0.66, 0.0, 0]}>
        <VrButton label={`${speed}x`} width={0.1} height={0.06} onClick={cycleSpeed} />
      </group>
      <Text position={[-0.7, -0.15, 0]} fontSize={0.024} color="#64748b" anchorX="left">
        {"A:play B:speed X:menu  R-stick:scale  L-stick:move"}
      </Text>
    </group>
  );
}

/** エピソード選択メニュー（プレイヤー左側）。 */
function EpisodeMenuPanel() {
  const episodes = useViewer((s) => s.episodes);
  const currentId = useViewer((s) => s.current?.id ?? null);
  const selectEpisode = useViewer((s) => s.selectEpisode);
  const setVrMenuOpen = useViewer((s) => s.setVrMenuOpen);
  const [page, setPage] = useState(0);
  const perPage = 5;
  const nPages = Math.max(1, Math.ceil(episodes.length / perPage));
  const pageClamped = Math.min(page, nPages - 1);
  const rows = useMemo(
    () => episodes.slice(pageClamped * perPage, pageClamped * perPage + perPage),
    [episodes, pageClamped],
  );

  return (
    <group position={[-0.85, 1.25, -0.65]} rotation={[-0.3, 0.5, 0]}>
      <mesh position={[0, 0, -0.01]}>
        <planeGeometry args={[0.9, 0.78]} />
        <meshStandardMaterial color="#020617" transparent opacity={0.88} roughness={0.9} />
      </mesh>
      <Text position={[0, 0.33, 0]} fontSize={0.036} color="#e2e8f0">
        Episodes
      </Text>
      {rows.map((ep, i) => (
        <group key={ep.id} position={[0, 0.22 - i * 0.11, 0]}>
          <VrButton
            label={`${ep.success === false ? "x" : "o"} ${ep.language.slice(0, 26) || ep.id}`}
            width={0.8}
            height={0.08}
            fontSize={0.026}
            primary={ep.id === currentId}
            onClick={() => {
              void selectEpisode(ep);
              setVrMenuOpen(false);
            }}
          />
        </group>
      ))}
      <group position={[-0.16, -0.31, 0]}>
        <VrButton label="<" width={0.1} height={0.07} onClick={() => setPage((pageClamped - 1 + nPages) % nPages)} />
      </group>
      <Text position={[0, -0.31, 0]} fontSize={0.028} color="#94a3b8">
        {`${pageClamped + 1}/${nPages}`}
      </Text>
      <group position={[0.16, -0.31, 0]}>
        <VrButton label=">" width={0.1} height={0.07} onClick={() => setPage((pageClamped + 1) % nPages)} />
      </group>
      <group position={[0.33, -0.31, 0]}>
        <VrButton label="close" width={0.14} height={0.07} onClick={() => setVrMenuOpen(false)} />
      </group>
    </group>
  );
}

/** コントローラ入力（ボタンイベント + スティック連続値）。 */
function VrInput() {
  const right = useXRInputSourceState("controller", "right");
  const left = useXRInputSourceState("controller", "left");
  const togglePlay = useViewer((s) => s.togglePlay);
  const cycleSpeed = useViewer((s) => s.cycleSpeed);
  const setVrMenuOpen = useViewer((s) => s.setVrMenuOpen);
  const vrMenuOpen = useViewer((s) => s.vrMenuOpen);
  const multiplySceneScale = useViewer((s) => s.multiplySceneScale);
  const scaleRef = useRef(0);

  useXRControllerButtonEvent(right, "a-button", (state) => {
    if (state === "pressed") togglePlay();
  });
  useXRControllerButtonEvent(right, "b-button", (state) => {
    if (state === "pressed") cycleSpeed();
  });
  useXRControllerButtonEvent(left, "x-button", (state) => {
    if (state === "pressed") setVrMenuOpen(!vrMenuOpen);
  });
  useXRControllerButtonEvent(left, "y-button", (state) => {
    if (state === "pressed") setVrMenuOpen(!vrMenuOpen);
  });

  useFrame((_, delta) => {
    // 右スティック縦 → シーンの拡大/縮小
    const axes = right?.inputSource?.gamepad?.axes;
    const ry = axes && axes.length > 3 ? axes[3] : 0;
    if (Math.abs(ry) > 0.2) {
      multiplySceneScale(Math.exp(ry * delta * 1.2));
      scaleRef.current = ry;
    } else {
      scaleRef.current = 0;
    }
  });
  return null;
}

/** VR セッション中のレイヤー全体。 */
export default function VrLayer() {
  const session = useXR((s) => s.session);
  const vrMenuOpen = useViewer((s) => s.vrMenuOpen);
  const originRef = useRef<THREE.Group>(null);
  useXRControllerLocomotion(originRef);

  if (!session) return null;
  return (
    <>
      <XROrigin ref={originRef} position={[0, 0, 1.3]} />
      <VrInput />
      <PlaybackPanel />
      {vrMenuOpen ? <EpisodeMenuPanel /> : null}
    </>
  );
}
