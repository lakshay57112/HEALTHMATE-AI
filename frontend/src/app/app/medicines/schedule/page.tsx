"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Check, Clock, Settings2, Utensils } from "lucide-react";
import { toast } from "sonner";
import { EmptyState, ErrorState, LoadingGrid, PageHeader, StatusPill } from "@/components/common";
import { DoseRow, SLOT_ICONS, type Dose } from "@/components/medicine";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, Input, Progress } from "@/components/ui/primitives";
import { api, useApi } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { fmtDateTime, fmtTime } from "@/lib/utils";

const SLOT_MEAL: Record<string, string> = { morning: "breakfast", afternoon: "lunch", evening: "snack", night: "dinner" };

function MealConfirm({ meal, onDone }: { meal: any; onDone: () => void }) {
  const { t } = useI18n();
  const [delay, setDelay] = useState(false);
  const [time, setTime] = useState("");
  const log = async (status: string, delayed_until?: string) => {
    try {
      const d = await api("/meals/log", { method: "POST", json: { meal: meal.meal, status, delayed_until } });
      d.advisories?.forEach((a: any) => toast.message(`${a.medicine}: ${a.advisory}`, { duration: 8000 }));
      toast.success(status === "done" ? "Meal confirmed" : status === "delayed" ? "Meal time updated" : "Noted");
      setDelay(false);
      onDone();
    } catch (e: any) {
      toast.error(e.message);
    }
  };
  if (meal.status === "done") return <span className="flex items-center gap-1.5 text-sm text-primary"><Check className="h-4 w-4" /> {t(meal.meal.charAt(0).toUpperCase() + meal.meal.slice(1))} done</span>;
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="flex items-center gap-1.5 text-muted"><Utensils className="h-4 w-4" />{t(meal.meal.charAt(0).toUpperCase() + meal.meal.slice(1))} {fmtTime(meal.delayed_until || meal.time)}{meal.status === "delayed" && " (delayed)"}</span>
      {delay ? (
        <>
          <Input type="time" className="h-9 w-32" value={time} onChange={(e) => setTime(e.target.value)} aria-label="New meal time" />
          <Button size="sm" disabled={!time} onClick={() => log("delayed", time)}>Save</Button>
          <Button size="sm" variant="ghost" onClick={() => setDelay(false)}>{t("Cancel")}</Button>
        </>
      ) : (
        <>
          <Button size="sm" variant="secondary" onClick={() => log("done")}>{t("Ate")}</Button>
          <Button size="sm" variant="outline" onClick={() => setDelay(true)}><Clock /> {t("Delayed")}</Button>
        </>
      )}
    </div>
  );
}

export default function SchedulePage() {
  const { t } = useI18n();
  const today = useApi<any>("/medicines/today");
  const meals = useApi<any>("/meals/today");
  const history = useApi<{ items: any[] }>("/medicines/history?days=7");
  useEffect(() => {
    const h = () => { today.reload(); history.reload(); };
    window.addEventListener("hm:doses-changed", h);
    return () => window.removeEventListener("hm:doses-changed", h);
  }, [today, history]);

  if (today.error) return <ErrorState message={today.error.message} onRetry={today.reload} />;
  const doses: Dose[] = today.data?.doses || [];
  const done = doses.filter((d) => ["taken", "skipped"].includes(d.status)).length;
  const mealBy = Object.fromEntries((meals.data?.items || []).map((m: any) => [m.meal, m]));

  return (
    <>
      <PageHeader back="/app/medicines" eyebrow={today.data ? new Date(today.data.date + "T00:00:00").toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" }) : ""} title={t("Today's medicines")}
        description="Times follow your meals. Tell us when you eat, and after-food reminders follow along (within safe limits)."
        actions={<><Button asChild variant="outline"><Link href="/app/nutrition/meals"><Utensils /> {t("Meal schedule")}</Link></Button><Button asChild variant="outline"><Link href="/app/settings/reminders"><Settings2 /> {t("Voice reminders")}</Link></Button></>} />
      {today.loading ? <LoadingGrid rows={4} className="lg:grid-cols-1 sm:grid-cols-1" /> : doses.length === 0 ? (
        <EmptyState icon={Clock} title="Nothing scheduled today" description="Add medicines or upload a prescription to build your schedule." action={<Button asChild><Link href="/app/medicines/upload">Upload prescription</Link></Button>} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
          <div className="space-y-6">
            <Card className="p-5">
              <div className="flex items-center justify-between text-sm"><span className="font-medium">{done} of {doses.length} done</span><span className="text-muted">{Math.round((done / doses.length) * 100)}%</span></div>
              <Progress value={(done / doses.length) * 100} className="mt-2.5 h-2.5" />
            </Card>
            {(["morning", "afternoon", "evening", "night"] as const).map((slot) => {
              const list = doses.filter((d) => d.slot === slot);
              const meal = mealBy[SLOT_MEAL[slot]];
              if (!list.length) return null;
              const Icon = SLOT_ICONS[slot];
              return (
                <section key={slot}>
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <h2 className="flex items-center gap-2 text-lg font-semibold"><Icon className="h-5 w-5 text-primary" /> {t(slot.charAt(0).toUpperCase() + slot.slice(1))}</h2>
                    {meal && list.some((d) => d.meal_relation !== "any") && <MealConfirm meal={meal} onDone={() => { meals.reload(); today.reload(); }} />}
                  </div>
                  <div className="space-y-2.5">{list.map((d) => <DoseRow key={d.schedule_id} dose={d} onChange={today.reload} />)}</div>
                </section>
              );
            })}
            {today.data?.as_needed?.length > 0 && (
              <section>
                <h2 className="mb-3 text-lg font-semibold">Only when needed</h2>
                <Card className="divide-y divide-line">{today.data.as_needed.map((m: any) => <div key={m.id} className="px-5 py-3 text-sm"><b>{m.name}</b> {m.strength} — {m.instructions || "take only if needed, as your doctor advised"}</div>)}</Card>
              </section>
            )}
          </div>
          <div className="space-y-4">
            <Card>
              <CardHeader><CardTitle>How times are set</CardTitle></CardHeader>
              <CardContent className="space-y-2 text-sm text-ink-soft">
                <p>• Before food: 30 min before the meal</p><p>• After food: 15 min after the meal</p><p>• Empty stomach: 60 min before breakfast</p><p>• Bedtime: 90 min after dinner</p>
                <p className="pt-2 text-[0.82rem] text-muted">If a meal is delayed, after-food reminders move with it by up to 2 hours. Beyond that, we&apos;ll ask you to check with your doctor. Doses are never changed automatically.</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Recent history</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {(history.data?.items || []).slice(0, 12).map((h) => (
                  <div key={h.id} className="flex items-center justify-between gap-2 text-sm">
                    <span className="truncate"><span className="mr-2 inline-block h-2 w-2 rounded-full" style={{ background: h.color || "#4D8B73" }} />{h.medicine} <span className="text-muted">{h.strength}</span></span>
                    <span className="flex shrink-0 items-center gap-2"><span className="text-[0.78rem] text-muted">{fmtDateTime(h.scheduled_for)}</span><StatusPill status={h.status} /></span>
                  </div>
                ))}
                {!history.data?.items?.length && <p className="text-sm text-muted">No history yet.</p>}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
