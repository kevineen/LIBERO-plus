"use client";

import { useEffect, useMemo, useState } from "react";

/** ごく簡易な Markdown → HTML（見出し・リスト・コード・リンク） */
function renderMarkdown(md: string): string {
  const escaped = md
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  const lines = escaped.split("\n");
  const out: string[] = [];
  let inCode = false;
  let inUl = false;

  const flushUl = () => {
    if (inUl) {
      out.push("</ul>");
      inUl = false;
    }
  };

  for (const raw of lines) {
    if (raw.startsWith("```")) {
      flushUl();
      if (!inCode) {
        out.push("<pre class=\"md-pre\"><code>");
        inCode = true;
      } else {
        out.push("</code></pre>");
        inCode = false;
      }
      continue;
    }
    if (inCode) {
      out.push(raw + "\n");
      continue;
    }
    if (raw.startsWith("|")) {
      flushUl();
      // テーブルはそのまま pre 風に
      out.push(`<div class="md-table-line mono">${raw}</div>`);
      continue;
    }
    const heading = raw.match(/^(#{1,3})\s+(.*)$/);
    if (heading) {
      flushUl();
      const level = heading[1].length;
      out.push(`<h${level}>${inline(heading[2])}</h${level}>`);
      continue;
    }
    if (/^[-*]\s+/.test(raw)) {
      if (!inUl) {
        out.push("<ul>");
        inUl = true;
      }
      out.push(`<li>${inline(raw.replace(/^[-*]\s+/, ""))}</li>`);
      continue;
    }
    flushUl();
    if (!raw.trim()) {
      out.push("<br/>");
      continue;
    }
    out.push(`<p>${inline(raw)}</p>`);
  }
  flushUl();
  if (inCode) out.push("</code></pre>");
  return out.join("\n");
}

function inline(s: string): string {
  return s
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, label, href) => {
      const h = String(href);
      if (h.endsWith(".md")) {
        const id = h.replace(/^\.\.\//, "").replace(/^docs\//, "").replace(/\.md$/, "");
        return `<a href="/docs/${id}">${label}</a>`;
      }
      if (h.startsWith("http")) {
        return `<a href="${h}" target="_blank" rel="noreferrer">${label}</a>`;
      }
      return `<a href="${h}">${label}</a>`;
    });
}

export function MarkdownView({ markdown }: { markdown: string }) {
  const html = useMemo(() => renderMarkdown(markdown), [markdown]);
  return <article className="md-body" dangerouslySetInnerHTML={{ __html: html }} />;
}

export function DocsPageClient({ initialId }: { initialId?: string }) {
  const [id, setId] = useState(initialId ?? "10_ops_ui");
  const [title, setTitle] = useState("");
  const [markdown, setMarkdown] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialId) setId(initialId);
  }, [initialId]);

  useEffect(() => {
    setError(null);
    void fetch(`/api/v1/docs/${encodeURIComponent(id)}`)
      .then(async (r) => {
        const d = await r.json();
        if (!r.ok) throw new Error(d.error ?? r.statusText);
        setTitle(d.title);
        setMarkdown(d.markdown);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [id]);

  return (
    <div className="docs-layout">
      <DocsSidebar activeId={id} onSelect={setId} />
      <div className="docs-main">
        <h1>{title || id}</h1>
        {error ? <p className="error">{error}</p> : <MarkdownView markdown={markdown} />}
      </div>
    </div>
  );
}

function DocsSidebar({
  activeId,
  onSelect,
}: {
  activeId: string;
  onSelect: (id: string) => void;
}) {
  const [docs, setDocs] = useState<{ id: string; title: string }[]>([]);
  useEffect(() => {
    void fetch("/api/v1/docs")
      .then((r) => r.json())
      .then((d) => setDocs(d.docs ?? []));
  }, []);
  return (
    <aside className="docs-nav">
      <h2>マニュアル</h2>
      <ul>
        {docs.map((d) => (
          <li key={d.id} className={d.id === activeId ? "active" : ""}>
            <button type="button" className="linkish" onClick={() => onSelect(d.id)}>
              {d.title}
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
