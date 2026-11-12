"use client";
import Link from "next/link";
import { useState } from "react";
import { ChevronRight, FileText, Plus, Search } from "lucide-react";
import { EmptyState, ErrorState, IconTile, LoadingGrid, PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Badge, Card, Input, NativeSelect } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { DOC_TYPES, fmtDateTime } from "@/lib/utils";

const STATUS: Record<string, { label: string; v: any }> = {
  uploaded: { label: "Queued", v: "default" }, processing: { label: "Reading…", v: "info" }, needs_review: { label: "Needs review", v: "warning" },
  verified: { label: "Verified", v: "success" }, failed: { label: "Failed", v: "danger" }, rejected: { label: "Discarded", v: "default" },
};

export default function DocumentsPage() {
  const { lang } = useI18n();
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const params = new URLSearchParams({ ...(q && { q }), ...(type && { doc_type: type }), ...(status && { status }) }).toString();
  const { data, error, loading, reload } = useApi<{ items: any[] }>(`/documents${params ? `?${params}` : ""}`, [params]);
  return (
    <>
      <PageHeader title="Documents" description="Everything you've uploaded, and what we did with it." actions={<Button asChild><Link href="/app/documents/new"><Plus /> Upload</Link></Button>} />
      <div className="mb-4 grid gap-2 sm:grid-cols-[1fr_200px_180px]">
        <div className="relative"><Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" /><Input className="pl-10" placeholder="Search by file name" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <NativeSelect value={type} onChange={(e) => setType(e.target.value)} aria-label="Type"><option value="">All types</option>{Object.entries(DOC_TYPES).filter(([k]) => k !== "auto").map(([k, v]) => <option key={k} value={k}>{v[lang]}</option>)}</NativeSelect>
        <NativeSelect value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status"><option value="">Any status</option>{Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</NativeSelect>
      </div>
      {error ? <ErrorState message={error.message} onRetry={reload} /> : loading ? <LoadingGrid rows={3} className="sm:grid-cols-1 lg:grid-cols-1" /> : !data?.items.length ? (
        <EmptyState icon={FileText} title="No documents found" description="Upload a prescription, report or doctor's note to get started." action={<Button asChild><Link href="/app/documents/new">Upload a document</Link></Button>} />
      ) : (
        <Card className="divide-y divide-line">
          {data.items.map((d) => (
            <Link key={d.id} href={`/app/documents/${d.id}`} className="flex items-center gap-3 px-5 py-4 hover:bg-background">
              <IconTile icon={FileText} tone={d.status === "needs_review" ? "warning" : d.status === "verified" ? "primary" : "muted"} />
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{d.filename}</div>
                <div className="text-sm text-muted">{DOC_TYPES[d.detected_type || d.declared_type]?.[lang] || "Document"} · {fmtDateTime(d.created_at)}{d.confidence != null ? ` · ${Math.round(d.confidence * 100)}% confidence` : ""}</div>
              </div>
              {d.flags?.includes("possible_injection") && <Badge variant="danger">Security flag</Badge>}
              <Badge variant={STATUS[d.status]?.v}>{STATUS[d.status]?.label || d.status}</Badge>
              <ChevronRight className="h-4 w-4 text-muted" />
            </Link>
          ))}
        </Card>
      )}
    </>
  );
}
