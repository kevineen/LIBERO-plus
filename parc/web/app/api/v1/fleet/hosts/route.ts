import { NextResponse } from "next/server";

import { parseFleetJson, runParcFleet } from "@/lib/parc-fleet";

export const dynamic = "force-dynamic";

export async function GET() {
  const proc = runParcFleet(["hosts"]);
  if (!proc.ok) {
    return NextResponse.json(
      { error: proc.stderr || proc.stdout || "parc-fleet hosts failed" },
      { status: 500 },
    );
  }
  try {
    const data = parseFleetJson(proc.stdout);
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e), raw: proc.stdout.slice(0, 500) },
      { status: 500 },
    );
  }
}
