import { DocsPageClient } from "@/components/DocsView";

export const dynamic = "force-dynamic";

export default function DocsIndexPage() {
  return (
    <div className="page">
      <section className="hero-band">
        <div>
          <p className="eyebrow">operations · manuals</p>
          <h1>Docs</h1>
          <p className="lede">セットアップ・実験管理・無人ループ・UI 操作をここから読めます。</p>
        </div>
      </section>
      <DocsPageClient initialId="10_ops_ui" />
    </div>
  );
}
