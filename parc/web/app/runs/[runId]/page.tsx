import Link from "next/link";
import { notFound } from "next/navigation";

import { ArtifactGallery, CategoryBars } from "@/components/RunDetailViews";
import { ResumeActions } from "@/components/ResumeActions";
import { getStore } from "@/lib/adapters";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ runId: string }> };

export default async function RunPage({ params }: Props) {
  const { runId } = await params;
  const run = await getStore().getRun(decodeURIComponent(runId));
  if (!run) notFound();

  return (
    <div className="page">
      <p className="crumb">
        <Link href="/">Runs</Link> / <span className="mono">{run.runId}</span>
        {" · "}
        <Link href="/docs/10_ops_ui">操作マニュアル</Link>
      </p>

      <header className="detail-head">
        <div>
          <h1>{run.name}</h1>
          <p className="muted mono">{run.runId}</p>
        </div>
        <div className="detail-stats">
          <div>
            <span className="muted">status</span>
            <strong>{run.status}</strong>
          </div>
          <div>
            <span className="muted">machine</span>
            <strong className="mono">{run.machineId ?? "—"}</strong>
          </div>
          <div>
            <span className="muted">success</span>
            <strong className="mono">
              {run.successRate == null ? "—" : run.successRate.toFixed(3)}
            </strong>
          </div>
          <div>
            <span className="muted">episodes</span>
            <strong className="mono">{run.nEpisodes ?? "—"}</strong>
          </div>
        </div>
      </header>

      <div className="tag-row">
        {run.tags.map((t) => (
          <span key={t} className="tag">
            {t}
          </span>
        ))}
      </div>

      {run.notes ? <p className="notes">{run.notes}</p> : null}

      <ResumeActions runId={run.runId} />

      <section className="panel">
        <header className="panel-head">
          <h2>Categories</h2>
        </header>
        <CategoryBars byCategory={run.metrics?.by_category} />
      </section>

      <section className="panel">
        <header className="panel-head">
          <h2>Preview</h2>
        </header>
        <ArtifactGallery artifacts={run.artifacts} />
      </section>

      <section className="panel">
        <header className="panel-head">
          <h2>Config / Meta</h2>
        </header>
        <pre className="code-block">
          {JSON.stringify({ config: run.config, meta: run.meta }, null, 2)}
        </pre>
      </section>
    </div>
  );
}
