import { NextResponse } from "next/server";

import { getStore, getLauncher } from "@/lib/adapters";
import {
  WEB_VERSION,
  getExperimentsDir,
  getParcRoot,
  jobsAllowed,
} from "@/lib/config";

export const dynamic = "force-dynamic";

export async function GET() {
  const store = getStore();
  const launcher = getLauncher();
  return NextResponse.json({
    ok: true,
    version: WEB_VERSION,
    parcRoot: getParcRoot(),
    experimentsDir: getExperimentsDir(),
    adapters: {
      store: store.id,
      launcher: launcher.id,
    },
    jobsAllowed: jobsAllowed(),
  });
}
