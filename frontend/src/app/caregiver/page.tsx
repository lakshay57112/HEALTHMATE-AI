"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AlertTriangle, Bell, CalendarClock, FileText, HeartHandshake, Loader2, Lock, LogOut, Phone, Siren, Users } from "lucide-react";
import { AdherenceBars, Ring } from "@/components/charts";
import { EmptyState, Logo, StatusPill } from "@/components/common";
import { LanguageToggle } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardContent, CardHeader, CardTitle, Skeleton } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { cn, fmtDate, fmtDateTime, fmtTime, initials, relDays } from "@/lib/utils";

function Locked({ label }: { label: string }) {
  return <div className="flex items-center gap-2 rounded-xl bg-muted-bg px-4 py-3 text-sm text-muted"><Lock className="h-4 w-4" />{label} — not shared with you</div>;
}

function CaregiverInner() {
  const { user, loading, logout } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const params = useSearchParams();
  const patients = useApi<{ items: any[] }>(user?.role === "caregiver" ? "/caregiver/patients" : null, [user?.id]);
  const notes = useApi<any>(user?.role === "caregiver" ? "/notifications?limit=10" : null, [user?.id]);
  const [sel, setSel] = useState<string | null>(params.get("patient"));
  const pid = sel || patients.data?.items[0]?.patient_id || null;
  const summary = useApi<any>(pid ? `/caregiver/patients/${pid}/summary` : null, [pid]);

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login?next=/caregiver");
    else if (user.role === "patient") router.replace("/app");
  }, [user, loading, router]);
  useEffect(() => {
    const id = setInterval(() => { summary.reload(); notes.reload(); }, 60000);
    return () => clearInterval(id);
  }, [summary, notes]);

  if (loading || !user || user.role !== "caregiver") return <div className="flex min-h-screen items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-muted" /></div>;
  const s = summary.data;
  const first = s?.patient.full_name.split(" ")[0];

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-line bg-background/85 backdrop-blur">
        <div className="container flex h-16 items-center justify-between">
          <div className="flex items-center gap-3"><Logo /><Badge variant="primary" className="hidden sm:inline-flex"><HeartHandshake /> Caregiver</Badge></div>
          <div className="flex items-center gap-1"><LanguageToggle /><Button variant="ghost" size="sm" onClick={logout}><LogOut /> <span className="hidden sm:inline">{t("Sign out")}</span></Button></div>
        </div>
      </header>
      <main className="container max-w-6xl py-8">
        <div className="mb-6"><div className="eyebrow">Caregiver dashboard</div><h1 className="mt-1 text-[1.9rem] font-semibold">Hello, {user.full_name.split(" ")[0]}</h1>
          <p className="text-muted">You see only what your family member has chosen to share.{user.is_demo && " Demo account with sample data."}</p></div>

        {patients.loading ? <Skeleton className="h-40" /> : !patients.data?.items.length ? (
          <EmptyState icon={Users} title="No one connected yet" description="When a family member invites you, open their invitation link to connect." />
        ) : (
          <>
            {patients.data.items.length > 1 && (
              <div className="mb-6 flex gap-2 overflow-x-auto">{patients.data.items.map((p) => <button key={p.patient_id} onClick={() => setSel(p.patient_id)} className={cn("h-11 rounded-xl border px-4 text-sm font-medium", pid === p.patient_id ? "border-primary bg-primary-100 text-primary-800" : "border-line")}>{p.full_name}</button>)}</div>
            )}
            {!s ? <Skeleton className="h-96" /> : (
              <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
                <div className="space-y-6">
                  <Card className="flex flex-col gap-5 p-6 sm:flex-row sm:items-center">
                    <span className="flex h-16 w-16 items-center justify-center rounded-full bg-primary-100 text-xl font-semibold text-primary-800">{initials(s.patient.full_name)}</span>
                    <div className="flex-1"><div className="text-xl font-semibold">{s.patient.full_name}</div><div className="capitalize text-muted">Your {s.relationship}</div></div>
                    {s.adherence && <div className="flex items-center gap-4"><Ring value={s.adherence.percent} size={84} stroke={8} /><div className="text-sm text-muted">7-day<br />adherence</div></div>}
                  </Card>

                  <Card>
                    <CardHeader><CardTitle>{first}&apos;s medicines today</CardTitle></CardHeader>
                    <CardContent className="space-y-2">
                      {!s.permissions.view_medicines ? <Locked label="Medicine schedule" /> : s.doses_today.length === 0 ? <p className="text-sm text-muted">No medicines scheduled today.</p> : s.doses_today.map((d: any, i: number) => (
                        <div key={i} className={cn("flex items-center justify-between gap-3 rounded-xl px-4 py-3", ["overdue", "missed"].includes(d.status) ? "bg-warning-bg/70" : "bg-background")}>
                          <div><div className="font-medium">{d.name} <span className="text-muted">{d.strength}</span></div><div className="text-sm text-muted tnum">{fmtTime(d.effective_time)} · {d.dosage || "as prescribed"}</div></div>
                          <StatusPill status={d.status} />
                        </div>
                      ))}
                      {s.doses_today?.some((d: any) => ["overdue", "missed"].includes(d.status)) && <p className="flex items-center gap-1.5 pt-1 text-sm text-warning-ink"><AlertTriangle className="h-4 w-4" />Some doses weren&apos;t confirmed. A gentle call may help.</p>}
                    </CardContent>
                  </Card>

                  {s.adherence && <Card><CardHeader><CardTitle>Last 7 days</CardTitle></CardHeader><CardContent><AdherenceBars daily={s.adherence.daily} height={140} /></CardContent></Card>}

                  <Card>
                    <CardHeader><CardTitle>Reports</CardTitle></CardHeader>
                    <CardContent className="space-y-2">
                      {!s.permissions.view_reports ? <Locked label="Medical reports" /> : (s.reports || []).length === 0 ? <p className="text-sm text-muted">No reports yet.</p> : s.reports.map((r: any) => (
                        <div key={r.id} className="flex items-center gap-3 rounded-xl bg-background px-4 py-3"><FileText className="h-5 w-5 text-muted" /><div className="flex-1"><div className="font-medium">{r.title}</div><div className="text-sm text-muted">{fmtDate(r.report_date)}</div></div>
                          <span className={cn("text-sm", r.abnormal_count ? "text-warning-ink" : "text-primary")}>{r.abnormal_count ? `${r.abnormal_count} outside range` : "All in range"}</span></div>
                      ))}
                    </CardContent>
                  </Card>
                  {s.permissions.view_measurements && s.measurements?.length > 0 && (
                    <Card><CardHeader><CardTitle>Recent readings</CardTitle></CardHeader><CardContent className="grid gap-2 sm:grid-cols-2">
                      {s.measurements.slice(0, 6).map((m: any) => <div key={m.id} className="rounded-xl bg-background px-4 py-2.5 text-sm"><span className="capitalize">{m.kind.replace("_", " ")}</span>: <b className="tnum">{m.value}{m.value2 ? `/${m.value2}` : ""}</b> {m.unit}<span className="text-muted"> · {relDays(m.measured_at)}{m.is_sample ? " · sample" : ""}</span></div>)}
                    </CardContent></Card>
                  )}
                </div>
                <div className="space-y-6">
                  {s.emergency && (
                    <Card className="border-danger/30 p-5">
                      <div className="flex items-center gap-2 font-semibold"><Siren className="h-5 w-5 text-danger" /> Emergency</div>
                      <div className="mt-3 space-y-2 text-sm">
                        {s.emergency.patient_phone && <a href={`tel:${s.emergency.patient_phone}`} className="flex items-center gap-2 text-primary"><Phone className="h-4 w-4" />Call {first}: {s.emergency.patient_phone}</a>}
                        {s.emergency.emergency_contact_phone && <a href={`tel:${s.emergency.emergency_contact_phone}`} className="flex items-center gap-2 text-primary"><Phone className="h-4 w-4" />{s.emergency.emergency_contact_name}: {s.emergency.emergency_contact_phone}</a>}
                        <Button asChild variant="danger" className="mt-2 w-full"><a href="tel:112">Call 112</a></Button>
                      </div>
                    </Card>
                  )}
                  <Card>
                    <CardHeader><CardTitle className="flex items-center gap-2"><CalendarClock className="h-4 w-4" /> Appointments</CardTitle></CardHeader>
                    <CardContent className="space-y-2">
                      {!s.permissions.view_appointments ? <Locked label="Appointments" /> : (s.appointments || []).length === 0 ? <p className="text-sm text-muted">No upcoming appointments.</p> : s.appointments.map((a: any) => (
                        <div key={a.id} className="rounded-xl bg-background px-4 py-3 text-sm"><div className="font-medium">{a.doctor_name} <span className="font-normal text-muted">· {a.specialization}</span></div><div className="text-muted">{relDays(a.scheduled_at)} · {new Date(a.scheduled_at).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}{a.clinic ? ` · ${a.clinic}` : ""}</div></div>
                      ))}
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader><CardTitle className="flex items-center gap-2"><Bell className="h-4 w-4" /> Alerts</CardTitle></CardHeader>
                    <CardContent className="space-y-2">
                      {(notes.data?.items || []).length === 0 && <p className="text-sm text-muted">No alerts.</p>}
                      {(notes.data?.items || []).map((n: any) => (
                        <div key={n.id} className={cn("rounded-xl px-4 py-3 text-sm", n.severity === "warning" ? "bg-warning-bg/70" : "bg-background")}><div className="font-medium">{n.title}</div><div className="text-ink-soft">{n.body}</div><div className="mt-1 text-[0.75rem] text-muted">{fmtDateTime(n.created_at)}</div></div>
                      ))}
                    </CardContent>
                  </Card>
                  <Card className="p-5 text-sm text-muted"><Lock className="mb-2 h-4 w-4" />{first} controls what you can see. Each time you open this page it&apos;s recorded in their activity log.</Card>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default function CaregiverPage() {
  return <Suspense><CaregiverInner /></Suspense>;
}

const _l = Link;
