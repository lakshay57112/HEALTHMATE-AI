"use client";
import { useEffect, useState } from "react";
import { Coffee, Moon, Soup, Sun, Utensils } from "lucide-react";
import { toast } from "sonner";
import { ErrorState, PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardContent, CardHeader, CardTitle, Field, Input, Skeleton } from "@/components/ui/primitives";
import { api, useApi } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { fmtTime } from "@/lib/utils";

const ICON: Record<string, any> = { breakfast: Coffee, lunch: Sun, snack: Soup, dinner: Moon };

export default function MealsPage() {
  const { t } = useI18n();
  const sched = useApi<any>("/meals/schedule");
  const today = useApi<any>("/meals/today");
  const [times, setTimes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (sched.data) setTimes(Object.fromEntries(sched.data.items.map((m: any) => [m.meal, m.time])));
  }, [sched.data]);
  if (sched.error) return <ErrorState message={sched.error.message} onRetry={sched.reload} />;

  const save = async () => {
    setErr(null);
    setBusy(true);
    try {
      await api("/meals/schedule", { method: "PUT", json: { meals: Object.entries(times).map(([meal, time]) => ({ meal, time })) } });
      toast.success("Meal times saved. Medicine reminders were updated.");
      sched.reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <PageHeader back="/app/nutrition" title={t("Meal schedule")} description="Your usual meal times. Before-food and after-food medicine reminders are timed from these." />
      <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
        <Card>
          <CardHeader><CardTitle>Usual meal times</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            {!sched.data ? <Skeleton className="h-64" /> : ["breakfast", "lunch", "snack", "dinner"].map((m) => {
              const Icon = ICON[m];
              return (
                <div key={m} className="flex items-center gap-4">
                  <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-secondary text-primary"><Icon className="h-5 w-5" /></span>
                  <Field label={t(m.charAt(0).toUpperCase() + m.slice(1))} className="flex-1"><Input type="time" value={times[m] || ""} onChange={(e) => setTimes({ ...times, [m]: e.target.value })} className="max-w-[200px]" /></Field>
                </div>
              );
            })}
            {err && <p className="text-sm text-danger-ink">{err}</p>}
            <Button onClick={save} loading={busy} size="lg" className="h-12 w-full sm:w-auto">{t("Save")}</Button>
          </CardContent>
        </Card>
        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle>Today</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {(today.data?.items || []).map((m: any) => (
                <div key={m.meal} className="flex items-center justify-between rounded-xl bg-background px-3.5 py-2.5 text-sm">
                  <span className="flex items-center gap-2"><Utensils className="h-4 w-4 text-muted" />{t(m.meal.charAt(0).toUpperCase() + m.meal.slice(1))} · {fmtTime(m.delayed_until || m.time)}</span>
                  <Badge variant={m.status === "done" ? "success" : m.status === "delayed" ? "warning" : "default"}>{m.status}</Badge>
                </div>
              ))}
              <p className="pt-1 text-[0.82rem] text-muted">Confirm meals from Today&apos;s medicines when you eat.</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Rules we use</CardTitle></CardHeader>
            <CardContent className="space-y-1.5 text-sm text-ink-soft">
              <p>Before food → 30 min before the meal</p><p>After food → 15 min after the meal</p><p>Empty stomach → 60 min before the meal</p><p>Bedtime → 90 min after dinner</p>
              <p className="pt-2 text-[0.82rem] text-muted">These rules only set reminder times. Your prescription&apos;s medicines and doses are never changed. Ask your doctor if a medicine needs a specific time.</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
