"use client";
import Link from "next/link";
import { useState } from "react";
import { ChevronRight, FileText, TrendingDown, TrendingUp, Upload } from "lucide-react";
import { ParameterTrend } from "@/components/charts";
import { EmptyState, ErrorState, IconTile, LoadingGrid, PageHeader, SampleBadge } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn, fmtDate } from "@/lib/utils";

export default function ReportsPage() {
  const { t, lang } = useI18n();
  const reports = useApi<{ items: any[] }>("/reports");
  const trends = useApi<{ items: any[] }>("/reports/trends");
  const [sel, setSel] = useState<string | null>(null);
  const items = trends.data?.items || [];
  const current = items.find((x) => x.canonical === sel) || items[0];

  return (
    <>
      <PageHeader title={t("Medical Reports")} description="Your lab results explained in simple language, with trends over time."
        actions={<Button asChild><Link href="/app/reports/upload"><Upload /> {t("Upload report")}</Link></Button>} />
      {reports.error ? <ErrorState message={reports.error.message} onRetry={reports.reload} /> : reports.loading ? <LoadingGrid /> : !reports.data?.items.length ? (
        <EmptyState icon={FileText} title="No reports yet" description="Upload a blood test or lab report. We'll read every value and explain what it means — without guessing." action={<Button asChild><Link href="/app/reports/upload">{t("Upload report")}</Link></Button>} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1.25fr_1fr]">
          <div className="space-y-3">
            {reports.data.items.map((r) => (
              <Link key={r.id} href={`/app/reports/${r.id}`}>
                <Card className="flex items-center gap-4 p-4 transition-shadow hover:shadow-soft">
                  <IconTile icon={FileText} tone={r.abnormal_count ? "warning" : "primary"} className="h-12 w-12" />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2"><span className="font-semibold">{r.title}</span>{r.is_sample && <SampleBadge />}</div>
                    <div className="text-sm text-muted">{fmtDate(r.report_date)} · {r.lab_name || "Laboratory"} · {r.parameter_count} results</div>
                  </div>
                  <div className="text-right">
                    <div className={cn("text-lg font-semibold tnum", r.abnormal_count ? "text-warning-ink" : "text-primary")}>{r.abnormal_count}</div>
                    <div className="text-[0.72rem] text-muted">outside range</div>
                  </div>
                  <ChevronRight className="h-5 w-5 text-muted" />
                </Card>
              </Link>
            ))}
          </div>
          <Card className="self-start">
            <CardHeader><div><CardTitle>Trends</CardTitle><p className="text-sm text-muted">Shaded band = your lab&apos;s normal range</p></div></CardHeader>
            <CardContent>
              {items.length === 0 ? <p className="text-sm text-muted">Trends appear when the same test is in more than one report.</p> : (
                <>
                  <div className="mb-4 flex flex-wrap gap-1.5">
                    {items.map((x) => (
                      <button key={x.canonical} onClick={() => setSel(x.canonical)} className={cn("h-9 rounded-lg border px-3 text-sm", current?.canonical === x.canonical ? "border-primary bg-primary-100 text-primary-800" : "border-line text-ink-soft hover:bg-muted-bg")}>
                        {lang === "hi" && x.label_hi ? x.label_hi : x.label}
                      </button>
                    ))}
                  </div>
                  {current && (
                    <>
                      <ParameterTrend history={current.history} />
                      {current.history.filter((h: any) => h.value != null).length >= 2 && (() => {
                        const h = current.history.filter((x: any) => x.value != null);
                        const d = +(h.at(-1).value - h.at(-2).value).toFixed(2);
                        return <p className="mt-3 flex items-center gap-1.5 text-sm text-muted">{d > 0 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />} {d > 0 ? "Up" : "Down"} {Math.abs(d)} {h.at(-1).unit} since {fmtDate(h.at(-2).date)}</p>;
                      })()}
                    </>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
