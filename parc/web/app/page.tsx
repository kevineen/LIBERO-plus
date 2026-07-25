import { JobPanel } from "@/components/JobPanel";
import { RunTable } from "@/components/RunTable";
import { getStore } from "@/lib/adapters";
import { getExperimentsDir, jobsAllowed } from "@/lib/config";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const store = getStore();
  const runs = await store.listRuns({ limit: 100 });

  return (
    <div className="page">
      <section className="hero-band">
        <div>
          <p className="eyebrow">LIBERO-plus · experiment console</p>
          <h1>Runs</h1>
          <p className="lede">
            Local registry at <code className="mono">{getExperimentsDir()}</code>
            {jobsAllowed() ? " · job launch on" : " · job launch off"}
            {" · "}
            <a href="/docs/10_ops_ui">操作マニュアル</a>
          </p>
        </div>
        <div className="stat-pills">
          <div>
            <span className="stat-n">{runs.length}</span>
            <span className="muted">listed</span>
          </div>
          <div>
            <span className="stat-n">{runs.filter((r) => r.hasMetrics).length}</span>
            <span className="muted">with metrics</span>
          </div>
        </div>
      </section>

      <RunTable runs={runs} />

      <div id="jobs" className="section-gap">
        <JobPanel />
      </div>
    </div>
  );
}
