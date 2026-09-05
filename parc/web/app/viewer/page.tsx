import type { Metadata } from "next";

import ViewerClient from "@/components/viewer/ViewerClient";

export const metadata: Metadata = {
  title: "Episode Viewer | parc",
  description: "収録済みデモの 3D 再生ビューア（ブラウザ / スマホ / Quest 3 WebXR）",
};

export default function ViewerPage() {
  return <ViewerClient />;
}
