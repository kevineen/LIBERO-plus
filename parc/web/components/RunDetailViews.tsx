import type { Artifact, CategoryStats } from "@/lib/types";

export function CategoryBars({
  byCategory,
}: {
  byCategory: Record<string, CategoryStats> | undefined;
}) {
  if (!byCategory || Object.keys(byCategory).length === 0) {
    return <p className="muted">No category metrics.</p>;
  }
  const entries = Object.entries(byCategory).sort((a, b) => a[0].localeCompare(b[0]));
  return (
    <div className="cat-list">
      {entries.map(([name, s]) => (
        <div key={name} className="cat-row">
          <div className="cat-label">
            <span>{name}</span>
            <span className="mono muted">
              n={s.n} · sr={Number(s.success_rate).toFixed(3)}
            </span>
          </div>
          <div className="bar-track">
            <div
              className="bar-fill"
              style={{ width: `${Math.max(0, Math.min(1, Number(s.success_rate))) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function ArtifactGallery({ artifacts }: { artifacts: Artifact[] }) {
  const media = artifacts.filter((a) => a.kind === "image" || a.kind === "video");
  const others = artifacts.filter((a) => a.kind !== "image" && a.kind !== "video");

  return (
    <div className="stack">
      {media.length > 0 ? (
        <div className="media-grid">
          {media.map((a) =>
            a.kind === "video" ? (
              <figure key={a.id} className="media-card">
                <video src={a.url} controls preload="metadata" />
                <figcaption className="mono muted">{a.label}</figcaption>
              </figure>
            ) : (
              <figure key={a.id} className="media-card">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={a.url} alt={a.label} />
                <figcaption className="mono muted">{a.label}</figcaption>
              </figure>
            )
          )}
        </div>
      ) : (
        <p className="muted">No frames/videos. Enable eval.save_video or save_frames.</p>
      )}

      <ul className="artifact-list">
        {others.map((a) => (
          <li key={a.id}>
            <a href={a.url} target="_blank" rel="noreferrer">
              {a.label}
            </a>
            <span className="muted mono">{a.kind}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
