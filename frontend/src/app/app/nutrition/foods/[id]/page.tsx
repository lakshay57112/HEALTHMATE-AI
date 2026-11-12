"use client";
import { useParams } from "next/navigation";
import { useState } from "react";
import { AlertTriangle, ArrowLeftRight, Check, Clock, IndianRupee, Leaf, Users } from "lucide-react";
import { toast } from "sonner";
import { ErrorState, PageHeader } from "@/components/common";
import { FoodImage } from "@/components/food";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardContent, CardHeader, CardTitle, NativeSelect, Skeleton } from "@/components/ui/primitives";
import { api, useApi } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function FoodDetail() {
  const { id } = useParams<{ id: string }>();
  const { t, lang } = useI18n();
  const { data, error, loading, reload } = useApi<any>(`/nutrition/foods/${id}`);
  const [meal, setMeal] = useState("");
  const [busy, setBusy] = useState(false);
  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (loading || !data) return <Skeleton className="h-96" />;
  const f = data.food;
  const macros = [["Calories", Math.round(f.calories), "kcal"], ["Protein", f.protein_g, "g"], ["Carbs", f.carbs_g, "g"], ["Fat", f.fat_g, "g"], ["Fibre", f.fibre_g, "g"], ["Sodium", Math.round(f.sodium_mg), "mg"]];
  const addToToday = async () => {
    setBusy(true);
    try {
      await api("/nutrition/plan/swap", { method: "PUT", json: { date: new Date().toLocaleDateString("en-CA"), meal: meal || f.meal_types[0], food_id: f.id } });
      toast.success(`Added to today's ${meal || f.meal_types[0]}`);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <PageHeader back="/app/nutrition" eyebrow={f.meal_types.map((m: string) => t(m.charAt(0).toUpperCase() + m.slice(1))).join(" · ")} title={lang === "hi" && f.name_hi ? f.name_hi : f.name} description={f.description} />
      <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        <div className="space-y-4">
          <FoodImage food={f} className="aspect-[4/3] rounded-3xl border border-line" />
          <div className="flex flex-wrap gap-2 text-sm">
            <Badge variant="outline"><Clock /> {f.prep_minutes} min</Badge><Badge variant="outline"><Users /> {f.serving}</Badge>
            <Badge variant="outline"><IndianRupee /> {f.cost_level === "low" ? "Budget" : f.cost_level === "moderate" ? "Moderate" : "Premium"}</Badge>
            <Badge variant="outline" className="capitalize">{f.diet.replace("_", "-")}</Badge>
            {f.allergens.map((a: string) => <Badge key={a} variant="warning">Contains {a}</Badge>)}
          </div>
          <div className="grid grid-cols-3 gap-2">
            {macros.map(([k, v, u]) => (
              <Card key={k as string} className="p-3 text-center"><div className="text-xl font-semibold tnum">{v}<span className="text-xs font-normal text-muted"> {u}</span></div><div className="text-[0.78rem] text-muted">{t(k as string)}</div></Card>
            ))}
          </div>
          <p className="text-[0.78rem] text-muted">Approximate values per serving · glycemic load: {f.glycemic}</p>
        </div>
        <div className="space-y-4">
          {data.suitable ? (
            <Card className="border-primary-200 bg-primary-50/50">
              <CardHeader><CardTitle className="flex items-center gap-2"><Leaf className="h-4 w-4 text-primary" />{t("Why this suits you")}</CardTitle></CardHeader>
              <CardContent><ul className="space-y-1.5 text-[0.95rem] text-ink-soft">{f.reasons.map((r: string) => <li key={r} className="flex gap-2"><Check className="mt-1 h-4 w-4 shrink-0 text-primary" />{r}</li>)}</ul></CardContent>
            </Card>
          ) : (
            <Card className="border-warning/40 bg-warning-bg/50 p-5 text-sm text-warning-ink"><AlertTriangle className="mb-2 h-5 w-5" />Not part of your plan: this doesn&apos;t fit your current rules ({data.not_suitable_reason}).</Card>
          )}
          <Card>
            <CardHeader><CardTitle>{t("Ingredients")}</CardTitle></CardHeader>
            <CardContent><ul className="grid gap-1.5 text-[0.95rem] sm:grid-cols-2">{f.ingredients.map((i: string) => <li key={i} className="flex gap-2"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />{i}</li>)}</ul></CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>{t("Preparation")}</CardTitle></CardHeader>
            <CardContent><ol className="space-y-3">{f.steps.map((s: string, i: number) => <li key={i} className="flex gap-3 text-[0.95rem]"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-secondary text-sm font-semibold text-primary-800">{i + 1}</span><span className="pt-0.5">{s}</span></li>)}</ol></CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><ArrowLeftRight className="h-4 w-4 text-primary" />{t("Substitutions")}</CardTitle></CardHeader>
            <CardContent><ul className="space-y-1.5 text-[0.95rem] text-ink-soft">{f.substitutions.map((s: string) => <li key={s}>• {s}</li>)}</ul></CardContent>
          </Card>
          {data.suitable && (
            <Card className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center">
              <NativeSelect value={meal} onChange={(e) => setMeal(e.target.value)} className="sm:w-48" aria-label="Meal">
                {f.meal_types.map((m: string) => <option key={m} value={m}>{t(m.charAt(0).toUpperCase() + m.slice(1))}</option>)}
              </NativeSelect>
              <Button onClick={addToToday} loading={busy} className="sm:flex-1">Use for today&apos;s meal</Button>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
