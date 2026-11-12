"use client";
import Link from "next/link";
import { useEffect } from "react";
import {
  Activity, ArrowRight, CalendarClock, Check, ChevronRight, Droplet, FileText, HeartPulse, MapPin, Pill, Plus, Scale, Sparkles, UserPlus, Users, Utensils,
} from "lucide-react";
import { AdherenceBars, Ring, Sparkline } from "@/components/charts";
import { EmptyState, ErrorState, IconTile, SampleBadge, StatusPill } from "@/components/common";
import { DoseRow, PillDot, SLOT_ICONS, type Dose } from "@/components/medicine";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardContent, CardHeader, CardTitle, Skeleton } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn, fmtDate, fmtTime, relDays } from "@/lib/utils";

const METRICS = [
  { kind: "blood_pressure", label: "Blood pressure", icon: HeartPulse, color: "#D96C6C" },
  { kind: "glucose", label: "Blood glucose", icon: Droplet, color: "#E9AA53" },
  { kind: "heart_rate", label: "Heart rate", icon: Activity, color: "#4D8B73" },
  { kind: "weight", label: "Weight", icon: Scale, color: "#6C8EBF" },
] as const;

function age(dob?: string | null) {
  if (!dob) return null;
  const d = new Date(dob);
  const n = new Date();
  return n.getFullYear() - d.getFullYear() - (n < new Date(n.getFullYear(), d.getMonth(), d.getDate()) ? 1 : 0);
}

export default function Dashboard() {
  const { t, lang } = useI18n();
  const { data, error, loading, reload } = useApi<any>("/dashboard");
  useEffect(() => {
    const h = () => reload();
    window.addEventListener("hm:doses-changed", h);
    return () => window.removeEventListener("hm:doses-changed", h);
  }, [reload]);

  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (loading || !data) return <DashboardSkeleton />;

  const u = data.user;
  const p = u.profile;
  const greeting = { morning: "Good morning", afternoon: "Good afternoon", evening: "Good evening" }[data.greeting as string] || "Hello";
  const next: Dose | null = data.next_dose;
  const doses: Dose[] = data.doses;
  const slots = (["morning", "afternoon", "evening", "night"] as const).map((s) => ({ slot: s, doses: doses.filter((d) => d.slot === s) })).filter((s) => s.doses.length);
  const allDone = doses.length > 0 && doses.every((d) => ["taken", "skipped"].includes(d.status));

  return (
    <div className="space-y-6">
      {/* Greeting */}
      <section className="flex flex-col gap-5 animate-fade-up md:flex-row md:items-end md:justify-between">
        <div>
          <div className="eyebrow mb-1.5">{new Date(data.now).toLocaleDateString(lang === "hi" ? "hi-IN" : "en-IN", { weekday: "long", day: "numeric", month: "long" })}</div>
          <h1 className="text-[1.9rem] font-semibold leading-tight sm:text-[2.2rem]">{t(greeting)}, {u.full_name.split(" ")[0]}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted">
            {age(p?.date_of_birth) && <span>{age(p.date_of_birth)} yrs</span>}
            {p?.blood_group && <><span className="text-line-strong">•</span><span>{p.blood_group}</span></>}
            {p?.conditions?.map((c: string) => <Badge key={c} variant="outline">{c}</Badge>)}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:flex">
          <Button asChild variant="outline" className="px-3 sm:px-5"><Link href="/app/assistant"><Sparkles /> {t("Ask a question")}</Link></Button>
          <Button asChild className="px-3 sm:px-5"><Link href="/app/documents/new"><Plus /> <span className="sm:hidden">Upload</span><span className="hidden sm:inline">{t("Upload a document")}</span></Link></Button>
        </div>
      </section>

      {data.pending_documents.some((d: any) => d.status === "needs_review") && (
        <Link href={`/app/documents/${data.pending_documents.find((d: any) => d.status === "needs_review").id}`}
          className="flex items-center gap-3 rounded-2xl border border-warning/40 bg-warning-bg/60 px-5 py-4 text-sm hover:bg-warning-bg">
          <FileText className="h-5 w-5 text-warning-ink" />
          <span className="flex-1"><span className="font-semibold text-warning-ink">{t("Needs your review")}:</span> {data.pending_documents.filter((d: any) => d.status === "needs_review").length} document(s) are ready — please check the details we read.</span>
          <ChevronRight className="h-4 w-4 text-warning-ink" />
        </Link>
      )}

      {/* Hero row */}
      <section className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2 overflow-hidden">
          <div className="flex h-full flex-col p-6">
            <div className="flex items-center justify-between">
              <span className="eyebrow">{t("Next medicine")}</span>
              <Link href="/app/medicines/schedule" className="text-sm font-medium text-primary hover:underline">{t("See schedule")}</Link>
            </div>
            {next ? (
              <div className="mt-4 flex flex-1 flex-col justify-between gap-5 sm:flex-row sm:items-end">
                <div className="flex items-center gap-4">
                  <PillDot color={next.color} className="h-16 w-16 rounded-2xl" />
                  <div>
                    <div className="text-[2.1rem] font-semibold leading-none tnum">{fmtTime(next.effective_time)}</div>
                    <div className="mt-2 text-lg font-medium">{next.name} <span className="text-muted">{next.strength}</span></div>
                    <div className="text-sm text-muted">{next.dosage || "As prescribed"} · {next.rule}</div>
                  </div>
                </div>
                {next.status === "due" ? <DoseRow dose={next} compact onChange={reload} /> : <StatusPill status={next.status} className="self-start sm:self-end" />}
              </div>
            ) : (
              <div className="mt-4 flex flex-1 items-center gap-4">
                <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-secondary text-primary">{allDone ? <Check className="h-7 w-7" /> : <Pill className="h-7 w-7" />}</span>
                <div>
                  <div className="text-lg font-semibold">{!doses.length ? t("No medicines yet") : allDone ? t("All done for today") : "No more doses today"}</div>
                  <p className="text-sm text-muted">{!doses.length ? "Upload a prescription and we'll build your reminder schedule."
                    : `${data.dose_summary.taken} of ${data.dose_summary.total} doses confirmed today.${data.dose_summary.attention ? ` ${data.dose_summary.attention} weren't confirmed — mark them if you took them.` : ""}`}</p>
                </div>
                {!doses.length && <Button asChild className="ml-auto"><Link href="/app/medicines/upload">{t("Upload prescription")}</Link></Button>}
              </div>
            )}
          </div>
        </Card>

        <Card>
          <div className="flex h-full flex-col p-6">
            <div className="flex items-center justify-between">
              <span className="eyebrow">{t("Medicine adherence")}</span>
              <span className="text-xs text-muted">{t("Last 7 days")}</span>
            </div>
            <div className="mt-4 flex items-center gap-5">
              <Ring value={data.adherence.percent} label="taken" />
              <div className="text-sm text-muted">
                <div><span className="text-xl font-semibold text-ink tnum">{data.adherence.taken}</span> / {data.adherence.expected} doses</div>
                <div className="mt-1">Today: {data.dose_summary.taken}/{data.dose_summary.total}{data.dose_summary.attention ? <span className="text-warning-ink"> · {data.dose_summary.attention} need attention</span> : null}</div>
              </div>
            </div>
            <div className="mt-auto pt-4"><AdherenceBars daily={data.adherence.daily} height={70} /></div>
          </div>
        </Card>
      </section>

      {/* Schedule + meals + appointment */}
      <section className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>{t("Today's medicines")}</CardTitle>
            <Link href="/app/medicines/schedule" className="text-sm font-medium text-primary hover:underline">{t("View all")}</Link>
          </CardHeader>
          <CardContent>
            {slots.length === 0 ? (
              <EmptyState icon={Pill} title={t("No medicines yet")} description="Add medicines manually or upload a prescription." action={<Button asChild size="sm"><Link href="/app/medicines/upload">{t("Upload prescription")}</Link></Button>} />
            ) : (
              <ol className="relative space-y-4 before:absolute before:bottom-2 before:left-[19px] before:top-2 before:w-px before:bg-line">
                {slots.map(({ slot, doses }) => {
                  const Icon = SLOT_ICONS[slot];
                  return (
                    <li key={slot} className="relative flex gap-4">
                      <span className="z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-line bg-surface text-muted"><Icon className="h-[1.1rem] w-[1.1rem]" /></span>
                      <div className="flex-1 space-y-2 pt-1.5">
                        <div className="text-sm font-semibold">{t(slot.charAt(0).toUpperCase() + slot.slice(1))}</div>
                        {doses.map((d) => (
                          <div key={d.schedule_id} className="flex items-center justify-between gap-3 rounded-xl bg-background px-3.5 py-2.5">
                            <div className="min-w-0 text-sm">
                              <span className="font-medium">{d.name}</span> <span className="text-muted">{d.strength}</span>
                              <div className="text-[0.8rem] text-muted tnum">{fmtTime(d.effective_time)} · {d.dosage || "as prescribed"}</div>
                            </div>
                            <StatusPill status={d.status} />
                          </div>
                        ))}
                      </div>
                    </li>
                  );
                })}
              </ol>
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("Upcoming appointment")}</CardTitle>
              <Link href="/app/appointments" aria-label="All appointments"><ArrowRight className="h-4 w-4 text-muted" /></Link>
            </CardHeader>
            <CardContent>
              {data.next_appointment ? (
                <div className="flex gap-3">
                  <div className="flex w-14 shrink-0 flex-col items-center rounded-xl bg-secondary py-2 text-primary-800">
                    <span className="text-[0.7rem] font-semibold uppercase">{new Date(data.next_appointment.scheduled_at).toLocaleDateString("en-IN", { month: "short" })}</span>
                    <span className="text-xl font-semibold leading-none tnum">{new Date(data.next_appointment.scheduled_at).getDate()}</span>
                  </div>
                  <div className="min-w-0">
                    <div className="font-semibold">{data.next_appointment.doctor_name}</div>
                    <div className="text-sm text-muted">{data.next_appointment.specialization}</div>
                    <div className="mt-1 text-sm text-ink-soft">{relDays(data.next_appointment.scheduled_at)} · {new Date(data.next_appointment.scheduled_at).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}</div>
                    {data.next_appointment.clinic && <div className="mt-0.5 flex items-center gap-1 text-[0.82rem] text-muted"><MapPin className="h-3.5 w-3.5" />{data.next_appointment.clinic}</div>}
                  </div>
                </div>
              ) : (
                <div className="text-sm text-muted">No upcoming appointments. <Link href="/app/appointments" className="font-medium text-primary">Add one</Link></div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t("Today's meals")}</CardTitle>
              <Link href="/app/nutrition" aria-label="Nutrition"><ArrowRight className="h-4 w-4 text-muted" /></Link>
            </CardHeader>
            <CardContent className="space-y-2.5">
              {data.meals.map((m: any) => (
                <div key={m.meal} className="flex items-center gap-3">
                  <IconTile icon={Utensils} tone={m.status === "done" ? "primary" : "muted"} className="h-9 w-9" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 text-sm"><span className="font-medium">{t(m.meal.charAt(0).toUpperCase() + m.meal.slice(1))}</span><span className="text-muted tnum">{fmtTime(m.time)}</span></div>
                    <div className="truncate text-[0.82rem] text-muted">{data.meal_plan_today?.[m.meal]?.map((f: any) => f.name).join(", ") || "—"}</div>
                  </div>
                  {m.status === "done" && <Check className="h-4 w-4 text-primary" />}
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Measurements */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{t("Health measurements")}</h2>
          {Object.values(data.measurements).flat().some((m: any) => m.is_sample) && <SampleBadge />}
        </div>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {METRICS.map((m) => {
            const series = data.measurements[m.kind] as any[];
            const last = series.at(-1);
            return (
              <Card key={m.kind} className="p-4">
                <div className="flex items-center gap-2 text-sm text-muted"><m.icon className="h-4 w-4" style={{ color: m.color }} />{t(m.label)}</div>
                <div className="mt-2 flex items-baseline gap-1">
                  <span className="text-2xl font-semibold tnum">{last ? (m.kind === "blood_pressure" ? `${last.value}/${last.value2}` : last.value) : "—"}</span>
                  <span className="text-sm text-muted">{last?.unit}</span>
                </div>
                <div className="text-[0.78rem] text-muted">{last ? `${relDays(last.measured_at)}${last.is_sample ? " · sample" : ""}` : "No readings yet"}</div>
                <div className="mt-2"><Sparkline data={series} color={m.color} /></div>
              </Card>
            );
          })}
        </div>
      </section>

      {/* Reports + family */}
      <section className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>{t("Recent reports")}</CardTitle>
            <Link href="/app/reports" className="text-sm font-medium text-primary hover:underline">{t("View all")}</Link>
          </CardHeader>
          <CardContent className="space-y-2">
            {data.recent_reports.length === 0 ? (
              <EmptyState icon={FileText} title="No reports yet" description="Upload a blood test or lab report to get a simple explanation." action={<Button asChild size="sm"><Link href="/app/reports/upload">{t("Upload report")}</Link></Button>} />
            ) : (
              data.recent_reports.map((r: any) => (
                <Link key={r.id} href={`/app/reports/${r.id}`} className="flex items-center gap-3 rounded-xl px-2 py-2.5 hover:bg-muted-bg">
                  <IconTile icon={FileText} tone={r.abnormal_count ? "warning" : "primary"} />
                  <div className="min-w-0 flex-1">
                    <div className="flex min-w-0 items-center gap-2"><span className="min-w-0 truncate font-medium">{r.title}</span>{r.is_sample && <SampleBadge className="hidden shrink-0 sm:inline-flex" />}</div>
                    <div className="truncate text-sm text-muted">{fmtDate(r.report_date)} · {r.lab_name || "Lab"}</div>
                    <div className={cn("text-[0.82rem] font-medium sm:hidden", r.abnormal_count ? "text-warning-ink" : "text-primary")}>{r.abnormal_count ? `${r.abnormal_count} outside range` : "All in range"}{r.is_sample ? " · sample" : ""}</div>
                  </div>
                  <span className={cn("hidden shrink-0 text-sm font-medium sm:inline", r.abnormal_count ? "text-warning-ink" : "text-primary")}>{r.abnormal_count ? `${r.abnormal_count} outside range` : "All in range"}</span>
                  <ChevronRight className="h-4 w-4 text-muted" />
                </Link>
              ))
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("Family connection")}</CardTitle>
            <Link href="/app/family" aria-label="Family"><ArrowRight className="h-4 w-4 text-muted" /></Link>
          </CardHeader>
          <CardContent>
            {data.family.length ? (
              <div className="space-y-3">
                {data.family.map((f: any) => (
                  <div key={f.name} className="flex items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-100 font-semibold text-primary-800">{f.name[0]}</span>
                    <div className="flex-1"><div className="font-medium">{f.name}</div><div className="text-sm capitalize text-muted">{f.relationship}</div></div>
                    <Badge variant={f.status === "active" ? "success" : "warning"}>{f.status === "active" ? t("Connected") : t("Invite pending")}</Badge>
                  </div>
                ))}
                <p className="pt-1 text-[0.82rem] text-muted"><Users className="mr-1 inline h-3.5 w-3.5" />They're alerted if a medicine is missed — only with your permission.</p>
              </div>
            ) : (
              <div className="text-center">
                <p className="text-sm text-muted">{t("Not connected")}. Let a family member get missed-medicine alerts.</p>
                <Button asChild size="sm" variant="secondary" className="mt-3"><Link href="/app/family"><UserPlus /> {t("Add family member")}</Link></Button>
              </div>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-16 w-72" />
      <div className="grid gap-4 lg:grid-cols-3"><Skeleton className="h-52 lg:col-span-2" /><Skeleton className="h-52" /></div>
      <div className="grid gap-4 lg:grid-cols-3"><Skeleton className="h-72 lg:col-span-2" /><Skeleton className="h-72" /></div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-36" />)}</div>
    </div>
  );
}

const _unused = CalendarClock;
