"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { CalendarClock, CalendarPlus, ClipboardList, FileText, MapPin, Pencil, Phone, Search, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import { EmptyState, ErrorState, LoadingGrid, PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Badge, Card, Field, Input, NativeSelect, Segmented, Textarea } from "@/components/ui/primitives";
import { api, useApi } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn, relDays } from "@/lib/utils";

const SPECS = ["General Physician", "Diabetologist", "Endocrinologist", "Cardiologist", "Nephrologist", "Neurologist", "Ophthalmologist", "Orthopaedic", "Dermatologist", "Pulmonologist", "Gastroenterologist", "Geriatrician", "Dentist", "Other"];

function toLocalInput(iso?: string) {
  const d = iso ? new Date(iso) : new Date(Date.now() + 86400000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function AppointmentDialog({ open, onOpenChange, appt, onSaved }: { open: boolean; onOpenChange: (o: boolean) => void; appt?: any; onSaved: () => void }) {
  const [f, setF] = useState<any>({});
  const [errs, setErrs] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) {
      setErrs({});
      setF(appt ? { ...appt, when: toLocalInput(appt.scheduled_at) } : { doctor_name: "", specialization: "General Physician", clinic: "", address: "", phone: "", when: toLocalInput(), notes: "", reminder_minutes_before: 120, status: "upcoming", consultation_summary: "" });
    }
  }, [open, appt]);
  const set = (k: string, v: any) => setF((p: any) => ({ ...p, [k]: v }));
  const save = async () => {
    const e: Record<string, string> = {};
    if (!f.doctor_name || f.doctor_name.trim().length < 2) e.doctor_name = "Enter the doctor's name";
    if (!f.when) e.when = "Choose date and time";
    setErrs(e);
    if (Object.keys(e).length) return;
    setBusy(true);
    try {
      const body = { doctor_name: f.doctor_name, specialization: f.specialization || null, clinic: f.clinic || null, address: f.address || null, phone: f.phone || null,
        scheduled_at: new Date(f.when).toISOString(), notes: f.notes || null, consultation_summary: f.consultation_summary || null, reminder_minutes_before: +f.reminder_minutes_before, status: f.status,
        prescription_id: f.prescription_id || null, document_id: f.document_id || null };
      await api(appt ? `/appointments/${appt.id}` : "/appointments", { method: appt ? "PUT" : "POST", json: body });
      toast.success(appt ? "Appointment updated" : "Appointment added — we'll remind you");
      onOpenChange(false);
      onSaved();
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={appt ? "Edit appointment" : "Add appointment"} wide>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Doctor" error={errs.doctor_name}><Input value={f.doctor_name || ""} onChange={(e) => set("doctor_name", e.target.value)} placeholder="Dr. …" /></Field>
          <Field label="Specialization"><NativeSelect value={f.specialization || ""} onChange={(e) => set("specialization", e.target.value)}>{SPECS.map((s) => <option key={s}>{s}</option>)}</NativeSelect></Field>
          <Field label="Date & time" error={errs.when}><Input type="datetime-local" value={f.when || ""} onChange={(e) => set("when", e.target.value)} /></Field>
          <Field label="Remind me"><NativeSelect value={f.reminder_minutes_before} onChange={(e) => set("reminder_minutes_before", e.target.value)}>{[[60, "1 hour before"], [120, "2 hours before"], [240, "4 hours before"], [1440, "1 day before"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</NativeSelect></Field>
          <Field label="Clinic / hospital"><Input value={f.clinic || ""} onChange={(e) => set("clinic", e.target.value)} /></Field>
          <Field label="Phone"><Input value={f.phone || ""} onChange={(e) => set("phone", e.target.value)} /></Field>
          <Field label="Address" className="sm:col-span-2"><Input value={f.address || ""} onChange={(e) => set("address", e.target.value)} /></Field>
          <Field label="Notes (what to bring, questions)" className="sm:col-span-2"><Textarea value={f.notes || ""} onChange={(e) => set("notes", e.target.value)} /></Field>
          {appt && (
            <>
              <Field label="Status"><NativeSelect value={f.status} onChange={(e) => set("status", e.target.value)}><option value="upcoming">Upcoming</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option></NativeSelect></Field>
              <Field label="Consultation summary" className="sm:col-span-2"><Textarea value={f.consultation_summary || ""} onChange={(e) => set("consultation_summary", e.target.value)} placeholder="What the doctor said" /></Field>
            </>
          )}
        </div>
        <div className="mt-5 flex justify-end gap-2"><Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button><Button onClick={save} loading={busy}>Save</Button></div>
      </DialogContent>
    </Dialog>
  );
}

export default function AppointmentsPage() {
  const { t } = useI18n();
  const [scope, setScope] = useState<"upcoming" | "past">("upcoming");
  const [q, setQ] = useState("");
  const { data, error, loading, reload } = useApi<{ items: any[] }>(`/appointments?scope=${scope}${q ? `&q=${encodeURIComponent(q)}` : ""}`, [scope, q]);
  const [dlg, setDlg] = useState<{ open: boolean; appt?: any }>({ open: false });
  const remove = async (a: any) => {
    if (!confirm(`Delete appointment with ${a.doctor_name}?`)) return;
    await api(`/appointments/${a.id}`, { method: "DELETE" });
    toast.success("Deleted");
    reload();
  };
  return (
    <>
      <PageHeader title={t("Appointments")} description="Upcoming visits, reminders and what the doctor said."
        actions={<><Button asChild variant="outline"><Link href="/app/documents/new"><Upload /> From a document</Link></Button><Button onClick={() => setDlg({ open: true })}><CalendarPlus /> Add appointment</Button></>} />
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Segmented value={scope} onChange={setScope} options={[{ value: "upcoming", label: "Upcoming" }, { value: "past", label: "History" }]} />
        <div className="relative sm:w-72"><Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" /><Input className="pl-10" placeholder="Search doctor or clinic" value={q} onChange={(e) => setQ(e.target.value)} /></div>
      </div>
      {error ? <ErrorState message={error.message} onRetry={reload} /> : loading ? <LoadingGrid rows={2} className="lg:grid-cols-2" /> : !data?.items.length ? (
        <EmptyState icon={CalendarClock} title={scope === "upcoming" ? "No upcoming appointments" : "No past appointments"} description="Add one manually, or upload an appointment slip and we'll fill it in." action={<Button onClick={() => setDlg({ open: true })}>Add appointment</Button>} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {data.items.map((a) => {
            const d = new Date(a.scheduled_at);
            return (
              <Card key={a.id} className={cn("p-5", a.status === "cancelled" && "opacity-60")}>
                <div className="flex gap-4">
                  <div className="flex w-16 shrink-0 flex-col items-center rounded-2xl bg-secondary py-2.5 text-primary-800">
                    <span className="text-[0.72rem] font-semibold uppercase">{d.toLocaleDateString("en-IN", { month: "short" })}</span>
                    <span className="text-2xl font-semibold leading-none tnum">{d.getDate()}</span>
                    <span className="mt-0.5 text-[0.72rem]">{d.toLocaleDateString("en-IN", { weekday: "short" })}</span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2"><span className="text-lg font-semibold">{a.doctor_name}</span>{a.status !== "upcoming" && <Badge>{a.status}</Badge>}{a.source !== "manual" && <Badge variant="outline">{a.source === "assistant" ? "Added via assistant" : "From document"}</Badge>}</div>
                    <div className="text-sm text-muted">{a.specialization}</div>
                    <div className="mt-2 text-[0.95rem] font-medium">{relDays(a.scheduled_at)} · {d.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}</div>
                    {a.clinic && <div className="mt-1 flex items-center gap-1.5 text-sm text-muted"><MapPin className="h-3.5 w-3.5" />{a.clinic}{a.address ? `, ${a.address}` : ""}</div>}
                    {a.phone && <a href={`tel:${a.phone}`} className="mt-1 flex items-center gap-1.5 text-sm text-primary"><Phone className="h-3.5 w-3.5" />{a.phone}</a>}
                  </div>
                </div>
                {a.notes && <p className="mt-4 rounded-xl bg-background px-3.5 py-2.5 text-sm text-ink-soft">{a.notes}</p>}
                {a.consultation_summary && <div className="mt-3 rounded-xl border border-line px-3.5 py-2.5 text-sm"><div className="mb-1 flex items-center gap-1.5 font-medium"><ClipboardList className="h-4 w-4 text-primary" />Consultation summary</div><p className="whitespace-pre-line text-ink-soft">{a.consultation_summary}</p></div>}
                <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-3">
                  {a.document_id && <Button asChild variant="ghost" size="sm"><Link href={`/app/documents/${a.document_id}`}><FileText /> Document</Link></Button>}
                  {a.prescription_id && <Button asChild variant="ghost" size="sm"><Link href="/app/medicines"><FileText /> Prescription</Link></Button>}
                  <div className="ml-auto flex gap-1">
                    <Button variant="ghost" size="sm" onClick={() => setDlg({ open: true, appt: a })}><Pencil /> Edit</Button>
                    <Button variant="ghost" size="icon-sm" onClick={() => remove(a)} aria-label="Delete"><Trash2 /></Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
      <AppointmentDialog open={dlg.open} appt={dlg.appt} onOpenChange={(o) => setDlg((d) => ({ ...d, open: o }))} onSaved={reload} />
    </>
  );
}
