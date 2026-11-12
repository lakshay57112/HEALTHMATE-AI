"use client";
import Link from "next/link";
import { useState } from "react";
import { CalendarDays, ClipboardList, FlaskConical, RefreshCw, ShieldAlert, Stethoscope, Upload, Utensils } from "lucide-react";
import { toast } from "sonner";
import { ErrorState, LoadingGrid, PageHeader } from "@/components/common";
import { FoodCard } from "@/components/food";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardContent, CardHeader, CardTitle, Segmented } from "@/components/ui/primitives";
import { api, useApi } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const KIND_STYLE: Record<string, { icon: any; cls: string; label: string }> = {
  doctor: { icon: Stethoscope, cls: "bg-primary-100 text-primary-800", label: "Doctor" },
  condition: { icon: ClipboardList, cls: "bg-info-bg text-[#3D5F8F]", label: "Your condition" },
  report: { icon: FlaskConical, cls: "bg-warning-bg text-warning-ink", label: "Report" },
  safety: { icon: ShieldAlert, cls: "bg-danger-bg text-danger-ink", label: "Safety" },
};
const MEALS = ["breakfast", "lunch", "snack", "dinner"] as const;

export default function NutritionPage() {
  const { t } = useI18n();
  const ov = useApi<any>("/nutrition/overview");
  const [cat, setCat] = useState<string>("");
  const [meal, setMeal] = useState<string>("");
  const recs = useApi<any>(`/nutrition/recommendations?${new URLSearchParams({ ...(cat && { category: cat }), ...(meal && { meal }) })}`, [cat, meal]);
  const [regen, setRegen] = useState(false);

  if (ov.error) return <ErrorState message={ov.error.message} onRetry={ov.reload} />;
  const d = ov.data;
  const totals: { cal: number; p: number; fib: number; na: number } | null = d?.today
    ? (Object.values(d.today.meals).flat() as any[]).reduce((a, f) => ({ cal: a.cal + f.calories, p: a.p + f.protein_g, fib: a.fib + f.fibre_g, na: a.na + f.sodium_mg }), { cal: 0, p: 0, fib: 0, na: 0 })
    : null;

  return (
    <>
      <PageHeader title={t("Nutrition")} description="Meals chosen around your doctor's advice, your reports and your preferences."
        actions={<>
          <Button asChild variant="outline"><Link href="/app/nutrition/meals"><Utensils /> {t("Meal schedule")}</Link></Button>
          <Button asChild variant="outline"><Link href="/app/nutrition/planner"><CalendarDays /> {t("Weekly meal planner")}</Link></Button>
          <Button loading={regen} onClick={async () => { setRegen(true); try { await api("/nutrition/plan/regenerate", { method: "POST" }); toast.success("New plan ready"); ov.reload(); } finally { setRegen(false); } }}><RefreshCw /> New plan</Button>
        </>} />
      {!d ? <LoadingGrid /> : (
        <div className="space-y-8">
          <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
            <Card>
              <CardHeader><div><CardTitle>Your plan follows these rules</CardTitle><p className="text-sm text-muted">Doctor&apos;s instructions always come first and are never contradicted.</p></div></CardHeader>
              <CardContent className="space-y-4">
                {d.rules.length === 0 && <p className="text-sm text-muted">No dietary rules yet. Upload your doctor&apos;s diet advice or a lab report to personalise your meals.</p>}
                <div className="space-y-2">
                  {d.rules.map((r: any, i: number) => {
                    const k = KIND_STYLE[r.kind];
                    return (
                      <div key={i} className="flex items-start gap-3 rounded-xl bg-background px-3.5 py-2.5">
                        <span className={cn("mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg", k.cls)}><k.icon className="h-4 w-4" /></span>
                        <div className="min-w-0 text-sm"><span className="font-semibold">{r.label}</span><span className="text-muted"> — {r.source}</span></div>
                      </div>
                    );
                  })}
                </div>
                {d.doctor_instructions.length > 0 && (
                  <div><div className="eyebrow mb-2">Doctor&apos;s written advice</div><ul className="space-y-1 text-sm text-ink-soft">{d.doctor_instructions.map((x: string) => <li key={x}>• {x}</li>)}</ul></div>
                )}
                <div className="flex flex-wrap gap-2 text-sm">
                  <Badge variant="outline" className="capitalize">{(d.diet || "").replace("_", "-")}</Badge>
                  {d.allergies.map((a: string) => <Badge key={a} variant="danger">No {a}</Badge>)}
                </div>
                {d.notes.map((n: string) => <p key={n} className="text-[0.85rem] text-muted">{n}</p>)}
                <Button asChild variant="link" size="sm"><Link href="/app/documents/new"><Upload className="h-4 w-4" /> Upload diet advice</Link></Button>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><div><CardTitle>Daily targets</CardTitle><p className="text-sm text-muted">{d.targets.note}</p></div></CardHeader>
              <CardContent className="space-y-3">
                {[["Calories", d.targets.calories, totals && `${Math.round(totals.cal)} kcal in today's plan`], ["Protein (g)", d.targets.protein_g, totals && `${Math.round(totals.p)} g planned`],
                  ["Fibre (g)", d.targets.fibre_g, totals && `${Math.round(totals.fib)} g planned`], ["Sodium (mg)", d.targets.sodium_mg, totals && `${Math.round(totals.na)} mg from planned meals`]]
                  .filter(([, v]) => v).map(([k, v, s]) => (
                    <div key={k as string} className="flex items-center justify-between gap-3 rounded-xl bg-background px-3.5 py-3">
                      <div><div className="text-sm font-medium">{k}</div><div className="text-[0.78rem] text-muted">{s}</div></div>
                      <div className="text-right font-semibold tnum">{v}</div>
                    </div>
                  ))}
              </CardContent>
            </Card>
          </div>

          <section>
            <div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-semibold">{t("Today's meals")}</h2><Link href="/app/nutrition/planner" className="text-sm font-medium text-primary hover:underline">Whole week</Link></div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {MEALS.map((m) => {
                const f = d.today?.meals?.[m]?.[0];
                return f ? <FoodCard key={m} food={f} meal={m} compact /> : <Card key={m} className="flex items-center justify-center p-6 text-sm text-muted">No suitable {m} found</Card>;
              })}
            </div>
          </section>

          <section>
            <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <h2 className="text-lg font-semibold">Explore foods for you</h2>
              <Segmented value={meal} onChange={setMeal} options={[{ value: "", label: "All" }, ...MEALS.map((m) => ({ value: m, label: t(m.charAt(0).toUpperCase() + m.slice(1)) }))]} />
            </div>
            <div className="mb-4 flex gap-2 overflow-x-auto pb-1 scrollbar-none">
              {[["", "All"], ...Object.entries(d.categories)].map(([k, v]: any) => (
                <button key={k} onClick={() => setCat(k)} className={cn("h-10 shrink-0 rounded-xl border px-3.5 text-sm font-medium", cat === k ? "border-primary bg-primary text-white" : "border-line-strong bg-surface text-ink-soft hover:bg-muted-bg")}>{v}</button>
              ))}
            </div>
            {recs.loading ? <LoadingGrid rows={4} className="lg:grid-cols-4" /> : (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">{recs.data?.items.map((f: any) => <FoodCard key={f.id} food={f} />)}</div>
                {recs.data?.items.length === 0 && <p className="text-sm text-muted">No foods match this filter with your current rules.</p>}
                {recs.data?.excluded?.length > 0 && <p className="mt-4 text-sm text-muted">{recs.data.excluded.length} foods are hidden because they don&apos;t fit your rules (for example: {recs.data.excluded.slice(0, 3).map((e: any) => `${e.name} — ${e.reason}`).join("; ")}).</p>}
              </>
            )}
            <p className="mt-6 text-[0.8rem] text-muted">Nutrition values are approximate per serving. Images are illustrations.</p>
          </section>
        </div>
      )}
    </>
  );
}
