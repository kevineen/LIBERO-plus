import { DocsPageClient } from "@/components/DocsView";

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ slug: string }> };

export default async function DocSlugPage({ params }: Ctx) {
  const { slug } = await params;
  return (
    <div className="page">
      <DocsPageClient initialId={decodeURIComponent(slug)} />
    </div>
  );
}
