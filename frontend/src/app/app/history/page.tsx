"use client";
import Link from "next/link";
import { useState } from "react";
import { Activity, CalendarClock, ClipboardCheck, FileText, History, Pill, Salad, Search, Smile } from "lucide-react";
import { toast } from "sonner";
import { EmptyState, ErrorState, LoadingGrid, PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, Field, Input, Textarea } from "@/components/ui/primitives";
import { api, useApi } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const CAT: Record<string, { label: string; icon: any; tone: string }> = {
  report: { label: "Reports", icon: FileText, tone: "bg-warning-bg text-warning-ink" },
  prescription: { label: "Prescriptions", icon: ClipboardCheck, tone: "bg-secondary text-primary" },
  document: { label: "Documents", icon: FileText, tone: "bg-muted-bg text-muted" },
  appointment: { label: "Appointments", icon: CalendarClock, tone: "bg-info-bg text-info" },
  measurement: { label: "Measurements", icon: Activity, tone: "bg-danger-bg text-danger" },
  medicine: { label: "Medicine log", icon: Pill, tone: "bg-secondary text-primary" },
  checkin: { label: "Check-ins", icon: Smile, tone: "bg-warning-bg text-warning-ink" },
  nutrition: { label: "Nutrition", icon: Salad, tone: "bg-secondary text-primary" },
};
const MOODS = [["great", "😊 Great"], ["good", "🙂 Good"], ["okay", "😐 Okay"], ["unwell", "🤒 Unwell"]];

function Checkin() {
  const today = useApi<any>("/checkins/today");
  const [mood, setMood] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const save = async () => {
    if (!mood) return;
    await api("/checkins", { method: "POST", json: { mood, note: note || null } });
    toast.success("Thanks for checking in");
    today.reload();
  };
  if (today.data?.checkin) return <Card className="p-5 text-sm"><span className="font-semibold">Today&apos;s check-in:</span> feeling {today.data.checkin.mood}{today.data.checkin.note ? ` — ${today.data.checkin.note}` : ""}</Card>;
  return (
    <Card className="p-5">
      <div className="font-semibold">How are you feeling today?</div>
      <div className="mt-3 flex flex-wrap gap-2">{MOODS.map(([k, l]) => <button key={k} onClick={() => setMood(k)} className={cn("h-11 rounded-xl border px-4 text-sm font-medium", mood === k ? "border-primary bg-primary-100 text-primary-800" : "border-line-strong hover:bg-muted-bg")}>{l}</button>)}</div>
      {mood && <Field label="Anything to note? (optional)" className="mt-3"><Textarea value={note} onChange={(e) => setNote(e.target.value)} className="min-h-[70px]" /></Field>}
      <Button className="mt-3" disabled={!mood} onClick={save}>Save check-in</Button>
      {mood === "unwell" && <p className="mt-3 text-sm text-warning-ink">If you feel very unwell, please contact your doctor. In an emergency call 112.</p>}
    </Card>
  );
}

export default function HistoryPage() {
  const { t } = useI18n();
  const [cats, setCats] = useState<string[]>([]);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [q, setQ] = useState("");
  const qs = new URLSearchParams({ ...(cats.length && { category: cats.join(",") }), ...(start && { start }), ...(end && { end }), ...(q && { q }) }).toString();
  const { data, error, loading, reload } = useApi<{ items: any[] }>(`/timeline${qs ? `?${qs}` : ""}`, [qs]);
  const groups: Record<string, any[]> = {};
  (data?.items || []).forEach((e) => (groups[new Date(e.at).toLocaleDateString("en-IN", { month: "long", year: "numeric" })] ||= []).push(e));

  return (
    <>
      <PageHeader title={t("Health History")} description="Everything in one timeline — reports, prescriptions, medicines, visits and readings." />
      <div className="mb-6"><Checkin /></div>
      <Card className="mb-6 space-y-4 p-4">
        <div className="flex flex-wrap gap-2">
          {Object.entries(CAT).map(([k, c]) => {
            const on = cats.includes(k);
            return <button key={k} onClick={() => setCats(on ? cats.filter((x) => x !== k) : [...cats, k])} className={cn("inline-flex h-9 items-center gap-1.5 rounded-lg border px-3 text-sm", on ? "border-primary bg-primary-100 text-primary-800" : "border-line text-ink-soft hover:bg-muted-bg")}><c.icon className="h-4 w-4" />{c.label}</button>;
          })}
        </div>
        <div className="grid gap-3 sm:grid-cols-[1fr_170px_170px]">
          <div className="relative"><Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" /><Input className="pl-10" placeholder="Search history" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} aria-label="From date" />
          <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} aria-label="To date" />
        </div>
      </Card>
      {error ? <ErrorState message={error.message} onRetry={reload} /> : loading ? <LoadingGrid rows={4} className="lg:grid-cols-1 sm:grid-cols-1" /> : !data?.items.length ? (
        <EmptyState icon={History} title="Nothing here yet" description="As you add documents, medicines and readings, they'll appear on your timeline." />
      ) : (
        <div className="space-y-8">
          {Object.entries(groups).map(([month, items]) => (
            <section key={month}>
              <h2 className="eyebrow mb-3">{month}</h2>
              <ol className="relative space-y-3 before:absolute before:bottom-3 before:left-5 before:top-3 before:w-px before:bg-line">
                {items.map((e) => {
                  const c = CAT[e.category];
                  return (
                    <li key={e.category + e.id} className="relative">
                      <Link href={e.link} className="flex items-start gap-4 rounded-2xl p-1 hover:bg-surface">
                        <span className={cn("z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full ring-4 ring-background", c.tone)}><c.icon className="h-[1.1rem] w-[1.1rem]" /></span>
                        <div className="min-w-0 flex-1 pt-1">
                          <div className="flex flex-wrap items-baseline justify-between gap-x-3"><span className="font-medium">{e.title}</span><span className="text-[0.8rem] text-muted">{new Date(e.at).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}</span></div>
                          {e.subtitle && <div className={cn("text-sm", e.severity === "warning" ? "text-warning-ink" : "text-muted")}>{e.subtitle}</div>}
                        </div>
                      </Link>
                    </li>
                  );
                })}
              </ol>
            </section>
          ))}
        </div>
      )}
    </>
  );
}
