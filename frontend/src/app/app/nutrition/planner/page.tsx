"use client";
import Link from "next/link";
import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { ErrorState, LoadingGrid, PageHeader } from "@/components/common";
import { FoodArt } from "@/components/food";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Card } from "@/components/ui/primitives";
import { api, useApi } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const MEALS = ["breakfast", "lunch", "snack", "dinner"] as const;

export default function PlannerPage() {
  const { t, lang } = useI18n();
  const { data, error, loading, reload, setData } = useApi<any>("/nutrition/plan");
  const [swap, setSwap] = useState<{ date: string; meal: string } | null>(null);
  const alts = useApi<any>(swap ? `/nutrition/recommendations?meal=${swap.meal}` : null, [swap?.meal]);
  const [busy, setBusy] = useState(false);
  const today = new Date().toLocaleDateString("en-CA");

  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  const plan = data?.plan;
  const doSwap = async (food_id: string) => {
    if (!swap) return;
    try {
      const d = await api("/nutrition/plan/swap", { method: "PUT", json: { ...swap, food_id } });
      setData(d);
      setSwap(null);
      toast.success("Meal swapped");
    } catch (e: any) {
      toast.error(e.message);
    }
  };
  return (
    <>
      <PageHeader back="/app/nutrition" title={t("Weekly meal planner")} description="Tap any meal to swap it for another option that fits your rules."
        actions={<Button loading={busy} onClick={async () => { setBusy(true); try { const d = await api("/nutrition/plan/regenerate", { method: "POST" }); setData(d); toast.success("New week planned"); } finally { setBusy(false); } }}><RefreshCw /> Regenerate week</Button>} />
      {loading || !plan ? <LoadingGrid rows={6} /> : (
        <div className="-mx-4 overflow-x-auto px-4 pb-2 sm:mx-0 sm:px-0">
          <div className="grid min-w-[880px] grid-cols-[110px_repeat(7,1fr)] gap-2">
            <div />
            {plan.days.map((d: any) => (
              <div key={d.date} className={cn("rounded-xl px-2 py-2 text-center text-sm", d.date === today ? "bg-primary text-white" : "text-ink-soft")}>
                <div className="font-semibold">{new Date(d.date + "T00:00:00").toLocaleDateString(lang === "hi" ? "hi-IN" : "en-IN", { weekday: "short" })}</div>
                <div className={cn("text-[0.75rem]", d.date === today ? "text-white/80" : "text-muted")}>{new Date(d.date + "T00:00:00").getDate()}</div>
              </div>
            ))}
            {MEALS.map((m) => (
              <div key={m} className="contents">
                <div className="flex items-center text-sm font-semibold text-ink-soft">{t(m.charAt(0).toUpperCase() + m.slice(1))}</div>
                {plan.days.map((d: any) => {
                  const f = d.meals[m]?.[0];
                  return (
                    <button key={d.date + m} onClick={() => setSwap({ date: d.date, meal: m })} className="card group overflow-hidden text-left transition-shadow hover:shadow-soft">
                      {f ? (
                        <>
                          <div className="h-16 overflow-hidden"><FoodArt slug={f.slug} className="scale-125" /></div>
                          <div className="p-2">
                            <div className="line-clamp-2 text-[0.8rem] font-medium leading-snug">{lang === "hi" && f.name_hi ? f.name_hi : f.name}</div>
                            <div className="mt-0.5 text-[0.72rem] text-muted tnum">{Math.round(f.calories)} kcal</div>
                          </div>
                        </>
                      ) : <div className="p-3 text-xs text-muted">—</div>}
                    </button>
                  );
                })}
              </div>
            ))}
            <div className="flex items-center text-sm font-semibold text-muted">Total</div>
            {plan.days.map((d: any) => (
              <div key={d.date + "t"} className="rounded-xl bg-muted-bg px-2 py-2 text-center text-[0.75rem] text-ink-soft tnum">
                <div className="font-semibold">{Math.round(d.totals.calories)} kcal</div>
                <div>P {Math.round(d.totals.protein_g)}g · F {Math.round(d.totals.fibre_g)}g</div>
              </div>
            ))}
          </div>
        </div>
      )}
      <Dialog open={!!swap} onOpenChange={(o) => !o && setSwap(null)}>
        <DialogContent title={`Swap ${swap?.meal || ""}`} description="Only foods that fit your doctor's advice and preferences are shown." wide>
          <div className="grid gap-2 sm:grid-cols-2">
            {(alts.data?.items || []).map((f: any) => (
              <button key={f.id} onClick={() => doSwap(f.id)} className="flex items-center gap-3 rounded-2xl border border-line p-2.5 text-left hover:border-primary-300 hover:bg-primary-50">
                <div className="h-14 w-14 shrink-0 overflow-hidden rounded-xl"><FoodArt slug={f.slug} /></div>
                <div className="min-w-0"><div className="truncate text-sm font-semibold">{f.name}</div><div className="text-[0.78rem] text-muted tnum">{Math.round(f.calories)} kcal · P {f.protein_g}g</div></div>
              </button>
            ))}
          </div>
          <Link href="/app/nutrition" className="mt-4 block text-sm text-primary">Browse all foods</Link>
        </DialogContent>
      </Dialog>
      <Card className="mt-6 p-4 text-[0.82rem] text-muted">Plans follow your doctor&apos;s instructions, allergies, food preference and report findings. High-protein foods are only suggested when your kidney markers and doctor&apos;s advice allow it.</Card>
    </>
  );
}
