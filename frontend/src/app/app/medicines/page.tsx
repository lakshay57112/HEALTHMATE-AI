"use client";
import Link from "next/link";
import { useState } from "react";
import { AlertTriangle, CalendarCheck, CalendarClock, ChevronRight, FileText, Package, Pencil, Pill, Plus, Upload, X } from "lucide-react";
import { toast } from "sonner";
import { AdherenceBars, Ring } from "@/components/charts";
import { EmptyState, ErrorState, LoadingGrid, PageHeader } from "@/components/common";
import { PillDot } from "@/components/medicine";
import { MedicineDialog } from "@/components/medicine-form";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardContent, CardHeader, CardTitle, Input } from "@/components/ui/primitives";
import { api, useApi } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { MEAL_REL, fmtDate, fmtTime } from "@/lib/utils";

export default function MedicinesPage() {
  const { t, lang } = useI18n();
  const meds = useApi<{ items: any[] }>("/medicines");
  const adherence = useApi<any>("/medicines/adherence?days=14");
  const today = useApi<any>("/medicines/today");
  const rx = useApi<{ items: any[] }>("/prescriptions");
  const [dialog, setDialog] = useState<{ open: boolean; med?: any }>({ open: false });
  const [stockEdit, setStockEdit] = useState<{ id: string; value: string } | null>(null);
  const reloadAll = () => { meds.reload(); today.reload(); adherence.reload(); };

  const scheduled = (meds.data?.items || []).filter((m) => !m.as_needed);
  const prn = (meds.data?.items || []).filter((m) => m.as_needed);
  const refills = (meds.data?.items || []).filter((m) => m.stock_count != null && m.stock_count <= m.refill_threshold);

  const stop = async (m: any) => {
    if (!confirm(`Stop reminders for ${m.name}? Only do this if your doctor told you to stop.`)) return;
    await api(`/medicines/${m.id}`, { method: "DELETE" });
    toast.success(`${m.name} stopped`);
    reloadAll();
  };
  const saveStock = async () => {
    if (!stockEdit) return;
    await api(`/medicines/${stockEdit.id}/stock`, { method: "PATCH", json: { stock_count: +stockEdit.value || 0 } });
    setStockEdit(null);
    meds.reload();
  };

  return (
    <>
      <PageHeader title={t("Medicines")} description="Your verified medicines, reminder times and adherence."
        actions={<>
          <Button asChild variant="outline"><Link href="/app/medicines/schedule"><CalendarCheck /> Today&apos;s schedule</Link></Button>
          <Button variant="outline" onClick={() => setDialog({ open: true })}><Plus /> {t("Add medicine")}</Button>
          <Button asChild><Link href="/app/medicines/upload"><Upload /> {t("Upload prescription")}</Link></Button>
        </>} />

      {meds.error ? <ErrorState message={meds.error.message} onRetry={meds.reload} /> : meds.loading ? <LoadingGrid /> : (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-3">
            <Card className="flex items-center gap-5 p-5">
              <Ring value={adherence.data?.percent ?? null} size={88} stroke={9} />
              <div><div className="eyebrow">Adherence</div><div className="mt-1 text-sm text-muted">{adherence.data ? `${adherence.data.taken} of ${adherence.data.expected} doses in 14 days` : "…"}</div></div>
            </Card>
            <Card className="p-5">
              <div className="eyebrow">Today</div>
              <div className="mt-2 text-3xl font-semibold tnum">{today.data?.summary?.taken ?? 0}<span className="text-lg text-muted"> / {today.data?.doses?.length ?? 0}</span></div>
              <div className="text-sm text-muted">doses confirmed{today.data?.next ? ` · next at ${fmtTime(today.data.next.effective_time)}` : ""}</div>
            </Card>
            <Card className="p-5">
              <div className="eyebrow">Refills</div>
              {refills.length ? (
                <div className="mt-2 space-y-1">{refills.map((m) => <div key={m.id} className="flex items-center gap-2 text-sm text-warning-ink"><AlertTriangle className="h-4 w-4" />{m.name}: {m.stock_count} left</div>)}</div>
              ) : <div className="mt-2 text-sm text-muted">No refills due. Add your tablet count to get reminders.</div>}
            </Card>
          </div>

          {scheduled.length === 0 && prn.length === 0 ? (
            <EmptyState icon={Pill} title={t("No medicines yet")} description="Upload a prescription and we'll extract each medicine for you to verify, or add one manually."
              action={<div className="flex gap-2"><Button asChild><Link href="/app/medicines/upload">{t("Upload prescription")}</Link></Button><Button variant="outline" onClick={() => setDialog({ open: true })}>{t("Add medicine")}</Button></div>} />
          ) : (
            <section>
              <h2 className="mb-3 text-lg font-semibold">Active medicines</h2>
              <div className="grid gap-3 md:grid-cols-2">
                {scheduled.map((m) => (
                  <Card key={m.id} className="p-5">
                    <div className="flex items-start gap-3">
                      <PillDot color={m.color} className="h-12 w-12" />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-lg font-semibold">{m.name}</span><span className="text-muted">{m.strength}</span>
                        </div>
                        <div className="text-sm text-muted">{m.generic_name && m.generic_name !== m.name ? `${m.generic_name} · ` : ""}{m.dosage || "as prescribed"} · {MEAL_REL[m.meal_relation]?.[lang]}</div>
                      </div>
                      <div className="flex gap-1">
                        <Button variant="ghost" size="icon-sm" aria-label={`Edit ${m.name}`} onClick={() => setDialog({ open: true, med: m })}><Pencil /></Button>
                        <Button variant="ghost" size="icon-sm" aria-label={`Stop ${m.name}`} onClick={() => stop(m)}><X /></Button>
                      </div>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-1.5">
                      {m.schedules.map((s: any) => <Badge key={s.id} variant="primary" title={s.rule} className="tnum">{fmtTime(s.time)} · {t(s.slot.charAt(0).toUpperCase() + s.slot.slice(1))}</Badge>)}
                    </div>
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3 text-[0.82rem] text-muted">
                      <span className="flex items-center gap-1.5"><CalendarClock className="h-3.5 w-3.5" />{m.end_date ? `Until ${fmtDate(m.end_date)}` : "Ongoing"}</span>
                      <span>{m.source === "prescription" ? <Badge variant="outline"><FileText /> From prescription</Badge> : <Badge variant="outline">Added by you</Badge>}</span>
                      {stockEdit?.id === m.id ? (
                        <span className="flex items-center gap-1.5"><Input type="number" className="h-9 w-20" value={stockEdit?.value ?? ""} onChange={(e) => setStockEdit({ id: m.id, value: e.target.value })} autoFocus /><Button size="sm" onClick={saveStock}>Save</Button></span>
                      ) : (
                        <button onClick={() => setStockEdit({ id: m.id, value: String(m.stock_count ?? "") })} className={`flex items-center gap-1.5 hover:text-ink ${m.stock_count != null && m.stock_count <= m.refill_threshold ? "font-medium text-warning-ink" : ""}`}>
                          <Package className="h-3.5 w-3.5" />{m.stock_count != null ? `${m.stock_count} left` : "Add stock"}
                        </button>
                      )}
                    </div>
                  </Card>
                ))}
              </div>
            </section>
          )}

          {prn.length > 0 && (
            <section>
              <h2 className="mb-3 text-lg font-semibold">Only when needed</h2>
              <div className="grid gap-3 md:grid-cols-2">
                {prn.map((m) => (
                  <Card key={m.id} className="flex items-center gap-3 p-4">
                    <PillDot color={m.color} />
                    <div className="flex-1"><div className="font-semibold">{m.name} <span className="font-normal text-muted">{m.strength}</span></div><div className="text-sm text-muted">{m.instructions || m.frequency || "As needed"} · no fixed reminder</div></div>
                    <Button variant="ghost" size="icon-sm" onClick={() => setDialog({ open: true, med: m })} aria-label="Edit"><Pencil /></Button>
                  </Card>
                ))}
              </div>
            </section>
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader><CardTitle>Last 14 days</CardTitle></CardHeader>
              <CardContent>{adherence.data && <AdherenceBars daily={adherence.data.daily} height={160} />}</CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Prescriptions</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {(rx.data?.items || []).length === 0 && <p className="text-sm text-muted">No verified prescriptions yet.</p>}
                {(rx.data?.items || []).map((p) => (
                  <Link key={p.id} href={p.document_id ? `/app/documents/${p.document_id}` : "#"} className="flex items-center gap-3 rounded-xl px-2 py-2.5 hover:bg-muted-bg">
                    <FileText className="h-5 w-5 text-muted" />
                    <div className="min-w-0 flex-1"><div className="font-medium">{p.doctor_name || "Doctor"}</div><div className="text-sm text-muted">{fmtDate(p.prescribed_date)} · {p.medicines.length} medicine(s){p.clinic ? ` · ${p.clinic}` : ""}</div></div>
                    {p.document_id && <ChevronRight className="h-4 w-4 text-muted" />}
                  </Link>
                ))}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
      <MedicineDialog open={dialog.open} medicine={dialog.med} onOpenChange={(o) => setDialog((d) => ({ ...d, open: o }))} onSaved={reloadAll} />
    </>
  );
}
