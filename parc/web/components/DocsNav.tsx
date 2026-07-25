"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type DocItem = {
  id: string;
  title: string;
  url: string;
};

/** サイドバー用マニュアル一覧 */
export function DocsNav({ activeId }: { activeId?: string }) {
  const [docs, setDocs] = useState<DocItem[]>([]);

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
            <Link href={d.url}>{d.title}</Link>
          </li>
        ))}
      </ul>
      <p className="muted small">
        運用の入口: <Link href="/docs/10_ops_ui">UI 操作マニュアル</Link>
      </p>
    </aside>
  );
}
