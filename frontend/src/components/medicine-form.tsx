"use client";
import { useEffect, useState } from "react";
import { Clock } from "lucide-react";
import { toast } from "sonner";
import { SLOT_ICONS } from "@/components/medicine";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Checkbox, Field, Input, NativeSelect } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { MEAL_REL, cn, fmtTime } from "@/lib/utils";

const SLOTS = ["morning", "afternoon", "evening", "night"] as const;
const blank = { name: "", strength: "", dosage: "1 tablet", form: "tablet", frequency: "", slots: [] as string[], meal_relation: "after_meal", as_needed: false, duration_days: "", start_date: "", instructions: "", stock_count: "", refill_threshold: 5 };

export function MedicineDialog({ open, onOpenChange, medicine, onSaved }: { open: boolean; onOpenChange: (o: boolean) => void; medicine?: any; onSaved: () => void }) {
  const { lang, t } = useI18n();
  const [f, setF] = useState<any>(blank);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<any[]>([]);

  useEffect(() => {
    if (open) {
      setErrors({});
      setF(medicine ? { ...blank, ...medicine, duration_days: medicine.duration_days ?? "", stock_count: medicine.stock_count ?? "", start_date: medicine.start_date || "" } : blank);
    }
  }, [open, medicine]);

  useEffect(() => {
    if (!open || f.as_needed) return setPreview([]);
    const freq = f.slots.length ? f.slots.map((s: string) => ({ morning: "1", afternoon: "1", evening: "1", night: "1" }[s])).join("") : "";
    const pattern = f.slots.length ? `${f.slots.includes("morning") ? 1 : 0}-${f.slots.includes("afternoon") ? 1 : 0}-${f.slots.includes("evening") ? 1 : 0}-${f.slots.includes("night") ? 1 : 0}` : f.frequency;
    if (!pattern && !freq) return setPreview([]);
    const id = setTimeout(() => {
      api(`/medicines/frequency-preview?frequency=${encodeURIComponent(pattern)}&meal_relation=${f.meal_relation}`).then((d) => setPreview(d.times || [])).catch(() => setPreview([]));
    }, 250);
    return () => clearTimeout(id);
  }, [open, f.slots, f.frequency, f.meal_relation, f.as_needed]);

  const set = (k: string, v: any) => setF((p: any) => ({ ...p, [k]: v }));
  const validate = () => {
    const e: Record<string, string> = {};
    if (!f.name || f.name.trim().length < 2) e.name = "Enter the medicine name as written on the strip";
    if (!f.as_needed && f.slots.length === 0 && !f.frequency) e.slots = "Choose at least one time, or tick 'only when needed'";
    if (f.duration_days && (+f.duration_days < 1 || +f.duration_days > 3650)) e.duration_days = "Enter between 1 and 3650 days";
    setErrors(e);
    return !Object.keys(e).length;
  };
  const save = async () => {
    if (!validate()) return;
    setBusy(true);
    const body = { ...f, duration_days: f.duration_days ? +f.duration_days : null, stock_count: f.stock_count === "" ? null : +f.stock_count, start_date: f.start_date || null,
      strength: f.strength || null, dosage: f.dosage || null, instructions: f.instructions || null, frequency: f.frequency || null };
    for (const k of ["id", "schedules", "verified", "is_active", "source", "color", "prescription_id", "end_date", "brand_name", "generic_name"]) delete body[k];
    try {
      await api(medicine ? `/medicines/${medicine.id}` : "/medicines", { method: medicine ? "PUT" : "POST", json: body });
      toast.success(medicine ? "Medicine updated" : "Medicine added — reminders are set");
      onOpenChange(false);
      onSaved();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={medicine ? `Edit ${medicine.name}` : t("Add medicine")} description="Enter exactly what your doctor prescribed. Reminder times follow your meal times." wide>
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Medicine name" error={errors.name}><Input value={f.name} onChange={(e) => set("name", e.target.value)} placeholder="e.g. Metformin" aria-invalid={!!errors.name} /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Strength"><Input value={f.strength || ""} onChange={(e) => set("strength", e.target.value)} placeholder="500mg" /></Field>
              <Field label="Form"><NativeSelect value={f.form || "tablet"} onChange={(e) => set("form", e.target.value)}>{["tablet", "capsule", "syrup", "injection", "drops", "inhaler", "other"].map((x) => <option key={x}>{x}</option>)}</NativeSelect></Field>
            </div>
            <Field label="Dose each time"><Input value={f.dosage || ""} onChange={(e) => set("dosage", e.target.value)} placeholder="1 tablet" /></Field>
            <Field label="Food timing"><NativeSelect value={f.meal_relation} onChange={(e) => set("meal_relation", e.target.value)}>{Object.entries(MEAL_REL).map(([k, v]) => <option key={k} value={k}>{v[lang]}</option>)}</NativeSelect></Field>
          </div>
          <label className="flex items-center gap-3 text-sm"><Checkbox checked={f.as_needed} onCheckedChange={(v) => set("as_needed", !!v)} /> Only when needed (SOS) — no fixed reminder</label>
          {!f.as_needed && (
            <Field label="When to take" error={errors.slots}>
              <div className="flex flex-wrap gap-2">
                {SLOTS.map((s) => {
                  const Icon = SLOT_ICONS[s];
                  const on = f.slots.includes(s);
                  return (
                    <button key={s} type="button" aria-pressed={on} onClick={() => set("slots", on ? f.slots.filter((x: string) => x !== s) : [...f.slots, s])}
                      className={cn("inline-flex h-12 items-center gap-2 rounded-xl border px-4 text-sm font-medium", on ? "border-primary bg-primary text-white" : "border-line-strong text-ink-soft hover:bg-muted-bg")}>
                      <Icon className="h-4 w-4" /> {t(s.charAt(0).toUpperCase() + s.slice(1))}
                    </button>
                  );
                })}
              </div>
            </Field>
          )}
          {preview.length > 0 && (
            <div className="rounded-xl bg-secondary/70 px-4 py-3 text-sm text-primary-800">
              <div className="mb-1 flex items-center gap-1.5 font-medium"><Clock className="h-4 w-4" /> Reminders will be at</div>
              {preview.map((p) => <div key={p.slot} className="tnum">{fmtTime(p.time)} — {p.rule}</div>)}
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Start date"><Input type="date" value={f.start_date || ""} onChange={(e) => set("start_date", e.target.value)} /></Field>
            <Field label="Duration (days)" error={errors.duration_days} hint="Leave empty if ongoing"><Input type="number" min={1} value={f.duration_days} onChange={(e) => set("duration_days", e.target.value)} /></Field>
            <Field label="Tablets in stock" hint="For refill reminders"><Input type="number" min={0} value={f.stock_count} onChange={(e) => set("stock_count", e.target.value)} /></Field>
          </div>
          <Field label="Instructions"><Input value={f.instructions || ""} onChange={(e) => set("instructions", e.target.value)} placeholder="Optional, as written by your doctor" /></Field>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>{t("Cancel")}</Button>
            <Button onClick={save} loading={busy}>{t("Save")}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
