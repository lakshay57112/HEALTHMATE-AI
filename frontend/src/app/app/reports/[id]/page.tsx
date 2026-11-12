"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { ArrowDownRight, ArrowUpRight, HelpCircle, Minus, Sparkles, Trash2, Volume2 } from "lucide-react";
import { toast } from "sonner";
import { ParameterTrend } from "@/components/charts";
import { Disclaimer, ErrorState, PageHeader, SampleBadge, StatusPill } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, Segmented, Skeleton } from "@/components/ui/primitives";
import { api, useApi } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn, fmtDate } from "@/lib/utils";
import { speak } from "@/lib/voice";

function RangeBar({ p }: { p: any }) {
  if (p.value == null || (p.ref_low == null && p.ref_high == null)) return <div className="h-1.5 w-full rounded-full bg-muted-bg" />;
  // Only printed bounds are drawn. A one-sided range ("< 200", "> 40") is drawn open-ended — no invented second bound.
  const pts = [p.value, p.ref_low, p.ref_high].filter((x: any) => x != null) as number[];
  const span = Math.max(...pts) - Math.min(...pts) || Math.abs(p.value) || 1;
  const min = Math.min(...pts) - span * 0.5;
  const max = Math.max(...pts) + span * 0.5;
  const pct = (x: number) => ((x - min) / (max - min)) * 100;
  const l = p.ref_low != null ? pct(p.ref_low) : 0;
  const r = p.ref_high != null ? pct(p.ref_high) : 100;
  const pos = Math.max(2, Math.min(98, pct(p.value)));
  return (
    <div className="relative h-1.5 w-full rounded-full bg-muted-bg" aria-hidden>
      <div className={cn("absolute inset-y-0 bg-primary-200", p.ref_low == null ? "rounded-l-full" : "rounded-l-sm", p.ref_high == null ? "rounded-r-full" : "rounded-r-sm")} style={{ left: `${l}%`, width: `${r - l}%` }} />
      <div className={cn("absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow", p.status === "high" ? "bg-danger" : p.status === "low" ? "bg-warning" : "bg-primary")} style={{ left: `${pos}%` }} />
    </div>
  );
}

export default function ReportDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { lang: uiLang, t } = useI18n();
  const [lang, setLang] = useState<"en" | "hi">(uiLang);
  const [sel, setSel] = useState<string | null>(null);
  const { data, error, loading, reload } = useApi<{ report: any }>(`/reports/${id}`);
  const r = data?.report;
  const hist = useApi<any>(r && (sel || r.parameters.find((p: any) => p.status !== "normal")?.canonical_name || r.parameters[0]?.canonical_name)
    ? `/reports/parameters/${sel || r.parameters.find((p: any) => p.status !== "normal")?.canonical_name || r.parameters[0]?.canonical_name}/history` : null, [sel, r?.id]);

  const groups = useMemo(() => {
    const g: Record<string, any[]> = {};
    (r?.parameters || []).forEach((p: any) => (g[p.test_group || "Results"] ||= []).push(p));
    return Object.entries(g);
  }, [r]);

  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (loading || !r) return <div className="space-y-4"><Skeleton className="h-12 w-80" /><Skeleton className="h-40" /><Skeleton className="h-96" /></div>;

  const s = r.summary?.[lang] || {};
  const counts = { high: 0, low: 0, normal: 0, unknown: 0 } as Record<string, number>;
  r.parameters.forEach((p: any) => counts[p.status]++);
  const abnormal = r.parameters.filter((p: any) => p.status === "high" || p.status === "low");

  return (
    <>
      <PageHeader back="/app/reports" eyebrow={<span className="flex items-center gap-2">{fmtDate(r.report_date)} · {r.lab_name || "Laboratory"} {r.is_sample && <SampleBadge />}</span>} title={r.title}
        actions={<>
          <Segmented value={lang} onChange={setLang} options={[{ value: "en", label: "English" }, { value: "hi", label: "हिंदी" }]} />
          <Button variant="outline" onClick={() => speak([s.headline, ...(s.findings || []).map((f: any) => f.text)].join(" "), { voice_language: lang === "hi" ? "hi-IN" : "en-IN" })} aria-label="Read aloud"><Volume2 /></Button>
          <Button asChild variant="secondary"><Link href={`/app/assistant?q=${encodeURIComponent(lang === "hi" ? "मेरी नवीनतम रिपोर्ट हिंदी में समझाइए" : "Explain my latest blood report")}`}><Sparkles /> Ask about this</Link></Button>
        </>} />

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-6">
          <Card className={cn("p-6", lang === "hi" && "lang-hi")}>
            <div className="eyebrow mb-2">{t("Simple explanation")}</div>
            <p className="text-[1.15rem] font-medium leading-relaxed">{s.headline}</p>
            <div className="mt-5 grid grid-cols-4 gap-2 text-center">
              {(["high", "low", "normal", "unknown"] as const).map((k) => (
                <div key={k} className="rounded-xl bg-background py-3"><div className="text-xl font-semibold tnum">{counts[k]}</div><div className="mt-0.5"><StatusPill status={k} /></div></div>
              ))}
            </div>
          </Card>

          {abnormal.length > 0 && (
            <section className={cn(lang === "hi" && "lang-hi")}>
              <h2 className="mb-3 text-lg font-semibold">{t("Important findings")}</h2>
              <div className="space-y-3">
                {abnormal.map((p: any) => {
                  const ex = r.explanations?.[p.id]?.[lang];
                  return (
                    <Card key={p.id} className={cn("cursor-pointer p-5 transition-shadow hover:shadow-soft", sel === p.canonical_name && "ring-2 ring-primary/30")} onClick={() => setSel(p.canonical_name)}>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="font-semibold">{ex?.label || p.name}</div>
                        <div className="flex items-center gap-2"><span className="text-lg font-semibold tnum">{p.value_text}</span><span className="text-sm text-muted">{p.unit}</span><StatusPill status={p.status} /></div>
                      </div>
                      <div className="mt-3"><RangeBar p={p} /></div>
                      <div className="mt-1 text-[0.78rem] text-muted">Lab range: {p.ref_text || "not printed"}</div>
                      <p className="mt-3 text-[0.95rem] text-ink-soft">{ex?.what} {ex?.meaning}</p>
                    </Card>
                  );
                })}
              </div>
            </section>
          )}

          <section>
            <h2 className="mb-3 text-lg font-semibold">{t("All results")}</h2>
            <Card className="divide-y divide-line">
              {groups.map(([g, ps]) => (
                <div key={g} className="px-5 py-4">
                  <div className="eyebrow mb-2">{g}</div>
                  <div className="divide-y divide-line/70">
                    {ps.map((p: any) => (
                      <button key={p.id} onClick={() => setSel(p.canonical_name)} className={cn("grid w-full grid-cols-[1fr_auto] items-center gap-x-4 gap-y-2 py-3 text-left sm:grid-cols-[1.2fr_0.8fr_1fr_auto]", sel === p.canonical_name && "bg-primary-50/60")}>
                        <span className="font-medium">{r.explanations?.[p.id]?.[lang]?.label || p.name}</span>
                        <span className="text-right tnum sm:text-left"><b>{p.value_text}</b> <span className="text-sm text-muted">{p.unit}</span></span>
                        <span className="col-span-2 sm:col-span-1"><RangeBar p={p} /><span className="mt-1 block text-[0.75rem] text-muted">{p.ref_text || "No range printed"}</span></span>
                        <StatusPill status={p.status} className="hidden sm:inline-flex" />
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </Card>
          </section>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader><div><CardTitle>{hist.data?.label || "Trend"}</CardTitle><p className="text-sm text-muted">Tap any result to see its history</p></div></CardHeader>
            <CardContent>{hist.data?.history?.length ? <ParameterTrend history={hist.data.history} /> : <Skeleton className="h-48" />}</CardContent>
          </Card>

          {r.comparison?.length > 0 && (
            <Card>
              <CardHeader><CardTitle>{t("Compared with last report")}</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {r.comparison.map((c: any) => (
                  <div key={c.canonical} className="flex items-center justify-between rounded-xl bg-background px-3.5 py-2.5 text-sm">
                    <span className="font-medium">{c.name}</span>
                    <span className="flex items-center gap-2 tnum text-muted">{c.previous} → <b className="text-ink">{c.current}</b>
                      {c.direction === "up" ? <ArrowUpRight className="h-4 w-4 text-warning-ink" /> : c.direction === "down" ? <ArrowDownRight className="h-4 w-4 text-primary" /> : <Minus className="h-4 w-4" />}
                    </span>
                  </div>
                ))}
                <p className="pt-1 text-[0.78rem] text-muted">Up or down isn&apos;t always good or bad — your doctor can explain what the change means for you.</p>
              </CardContent>
            </Card>
          )}

          <Card className={cn(lang === "hi" && "lang-hi")}>
            <CardHeader><CardTitle className="flex items-center gap-2"><HelpCircle className="h-4 w-4 text-primary" />{t("Questions to ask your doctor")}</CardTitle></CardHeader>
            <CardContent><ol className="list-decimal space-y-2 pl-5 text-[0.95rem] text-ink-soft">{(s.questions || []).map((q: string) => <li key={q}>{q}</li>)}</ol></CardContent>
          </Card>

          <Disclaimer>{s.disclaimer}</Disclaimer>
          {!r.is_sample && (
            <Button variant="ghost" size="sm" onClick={async () => { if (confirm("Delete this report?")) { await api(`/reports/${r.id}`, { method: "DELETE" }); toast.success("Report deleted"); router.push("/app/reports"); } }}>
              <Trash2 /> Delete report
            </Button>
          )}
        </div>
      </div>
    </>
  );
}
