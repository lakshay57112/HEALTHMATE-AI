"use client";
import { useState } from "react";
import { AlertTriangle, CircleAlert, CircleCheck, Info, Plus, Trash2 } from "lucide-react";
import { StatusPill } from "@/components/common";
import { SLOT_ICONS } from "@/components/medicine";
import { Button } from "@/components/ui/button";
import { Badge, Checkbox, Field, Input, NativeSelect, Textarea } from "@/components/ui/primitives";
import { useI18n } from "@/lib/i18n";
import { MEAL_REL, cn } from "@/lib/utils";

export type Flag = { code: string; message: string; severity: "high" | "warning" | "info"; path: string | null };
export type ItemReview = { index: number; confidence: number; flags: Flag[]; canonical?: string };

/* ---------- deterministic helpers mirrored from the backend ---------- */
export function parseRange(ref?: string | null): [number | null, number | null] {
  if (!ref) return [null, null];
  const r = ref.replace(",", ".").trim();
  let m = r.match(/^(\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(\d+(?:\.\d+)?)/);
  if (m) return [parseFloat(m[1]), parseFloat(m[2])];
  m = r.match(/^(?:<|<=|≤|up\s*to)\s*(\d+(?:\.\d+)?)/i);
  if (m) return [null, parseFloat(m[1])];
  m = r.match(/^(?:>|>=|≥)\s*(\d+(?:\.\d+)?)/);
  if (m) return [parseFloat(m[1]), null];
  return [null, null];
}
export function labStatus(value: string, ref?: string | null, lo?: number | null, hi?: number | null) {
  const v = parseFloat(String(value).replace(/[<>]/g, "").replace(",", "."));
  let [l, h] = [lo ?? null, hi ?? null];
  if (l == null && h == null) [l, h] = parseRange(ref);
  if (isNaN(v) || (l == null && h == null)) return "unknown";
  if (l != null && v < l) return "low";
  if (h != null && v > h) return "high";
  return "normal";
}
const FREQ: Record<string, string[]> = {
  od: ["morning"], qd: ["morning"], "once daily": ["morning"], bd: ["morning", "night"], bid: ["morning", "night"], "twice daily": ["morning", "night"],
  tds: ["morning", "afternoon", "night"], tid: ["morning", "afternoon", "night"], qid: ["morning", "afternoon", "evening", "night"], hs: ["night"], "at bedtime": ["night"],
};
const NON_DAILY = /\b(once a week|once weekly|weekly|every week|once in a week|alternate days?|every other day|once a month|monthly|hafte mein ek baar)\b/;
export function parseFrequency(f?: string | null): { slots: string[]; asNeeded: boolean; recognized: boolean; nonDaily?: boolean } {
  if (!f) return { slots: [], asNeeded: false, recognized: false };
  const s = f.trim().toLowerCase();
  if (/(sos|prn|as needed|when required|if needed)/.test(s)) return { slots: [], asNeeded: true, recognized: true };
  // weekly / alternate-day doses: only daily reminders exist, so these are saved without one (never as a daily schedule)
  if (NON_DAILY.test(s)) return { slots: [], asNeeded: true, recognized: true, nonDaily: true };
  const m = s.match(/^([01½])\s*-\s*([01½])\s*-\s*([01½])(?:\s*-\s*([01½]))?$/);
  if (m) {
    const parts = m.slice(1).filter((x) => x !== undefined);
    const map = parts.length === 3 ? ["morning", "afternoon", "night"] : ["morning", "afternoon", "evening", "night"];
    const slots = map.filter((_, i) => parts[i] !== "0");
    return { slots, asNeeded: false, recognized: slots.length > 0 };
  }
  for (const k of Object.keys(FREQ).sort((a, b) => b.length - a.length)) if (new RegExp(`\\b${k}\\b`).test(s)) return { slots: FREQ[k], asNeeded: false, recognized: true };
  return { slots: [], asNeeded: false, recognized: false };
}

/* ---------- shared UI ---------- */
export function FlagList({ flags, className }: { flags: Flag[]; className?: string }) {
  if (!flags?.length) return null;
  const order = { high: 0, warning: 1, info: 2 } as const;
  return (
    <ul className={cn("space-y-1.5", className)}>
      {[...flags].sort((a, b) => order[a.severity] - order[b.severity]).map((f, i) => {
        const Icon = f.severity === "high" ? CircleAlert : f.severity === "warning" ? AlertTriangle : Info;
        return (
          <li key={i} className={cn("flex items-start gap-2 rounded-lg px-3 py-2 text-[0.85rem]",
            f.severity === "high" ? "bg-danger-bg text-danger-ink" : f.severity === "warning" ? "bg-warning-bg text-warning-ink" : "bg-muted-bg text-ink-soft")}>
            <Icon className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{f.message}</span>
          </li>
        );
      })}
    </ul>
  );
}

export function ConfidenceChip({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.72rem] font-semibold tnum",
      pct >= 85 ? "bg-primary-100 text-primary-800" : pct >= 70 ? "bg-warning-bg text-warning-ink" : "bg-danger-bg text-danger-ink")} title="How sure we are that this was read correctly">
      {pct}% sure
    </span>
  );
}

/* ---------- Lab report ---------- */
export function LabEditor({ data, setData, items }: { data: any; setData: (d: any) => void; items: ItemReview[] }) {
  const upd = (i: number, k: string, v: any) => {
    const tests = data.tests.map((t: any, j: number) => (j === i ? { ...t, [k]: v, ...(k === "ref_text" ? { ref_low: null, ref_high: null } : {}) } : t));
    setData({ ...data, tests });
  };
  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Report title"><Input value={data.title || ""} onChange={(e) => setData({ ...data, title: e.target.value })} placeholder="e.g. Lipid profile" /></Field>
        <Field label="Laboratory"><Input value={data.lab_name || ""} onChange={(e) => setData({ ...data, lab_name: e.target.value })} /></Field>
        <Field label="Report date"><Input type="date" value={data.report_date || ""} onChange={(e) => setData({ ...data, report_date: e.target.value })} /></Field>
      </div>
      <div className="overflow-hidden rounded-2xl border border-line">
        <div className="hidden grid-cols-[1.6fr_0.8fr_0.8fr_1fr_auto_auto] gap-2 bg-background px-3 py-2.5 text-[0.75rem] font-semibold uppercase tracking-wide text-muted md:grid">
          <span>Test</span><span>Result</span><span>Unit</span><span>Lab range</span><span>Status</span><span />
        </div>
        <div className="divide-y divide-line">
          {data.tests.map((t: any, i: number) => {
            const rev = items.find((x) => x.index === i);
            const attention = rev && (rev.confidence < 0.75 || rev.flags.some((f) => f.severity === "high"));
            return (
              <div key={i} className={cn("px-3 py-3", attention && "bg-warning-bg/40")}>
                <div className="grid grid-cols-2 gap-2 md:grid-cols-[1.6fr_0.8fr_0.8fr_1fr_auto_auto] md:items-center">
                  <Input className="col-span-2 h-10 md:col-span-1" aria-label="Test name" value={t.name} onChange={(e) => upd(i, "name", e.target.value)} />
                  <Input className="h-10 tnum" aria-label="Result" value={t.value_text} onChange={(e) => upd(i, "value_text", e.target.value)} />
                  <Input className="h-10" aria-label="Unit" value={t.unit || ""} onChange={(e) => upd(i, "unit", e.target.value)} />
                  <Input className="h-10" aria-label="Reference range" placeholder="as printed" value={t.ref_text || ""} onChange={(e) => upd(i, "ref_text", e.target.value)} />
                  <div className="flex items-center gap-2"><StatusPill status={labStatus(t.value_text, t.ref_text, t.ref_low, t.ref_high)} />{rev && <ConfidenceChip value={rev.confidence} />}</div>
                  <Button variant="ghost" size="icon-sm" aria-label="Remove row" onClick={() => setData({ ...data, tests: data.tests.filter((_: any, j: number) => j !== i) })}><Trash2 /></Button>
                </div>
                {rev?.flags?.length ? <FlagList flags={rev.flags} className="mt-2" /> : null}
              </div>
            );
          })}
        </div>
      </div>
      <Button variant="outline" size="sm" onClick={() => setData({ ...data, tests: [...data.tests, { name: "", value_text: "", unit: "", ref_text: "" }] })}><Plus /> Add a test row</Button>
    </div>
  );
}

/* ---------- Prescription ---------- */
const SLOTS = ["morning", "afternoon", "evening", "night"] as const;

type Gap = { text: string; level: "required" | "check" | "info" };
// Server flags already covered by the live checks below (those update as the patient edits; flags don't).
const COVERED = new Set(["unclear_frequency", "missing_frequency", "missing_dosage", "missing_strength", "missing_duration", "as_needed", "non_daily"]);

/** What the paper didn't say for one medicine. Live: recomputed as the patient fills things in. */
export function medicineGaps(m: any, rev?: ItemReview): Gap[] {
  const gaps: Gap[] = [];
  const fp = parseFrequency(m.frequency);
  const slots: string[] = m.slots ?? fp.slots;
  if (fp.nonDaily) gaps.push({ level: "check", text: `Taken ${m.frequency?.toLowerCase()}, not daily — no daily reminder will be set` });
  else if (fp.asNeeded) gaps.push({ level: "check", text: "No time written — it says SOS (only when needed), so no reminder will be set" });
  else if (!slots.length) gaps.push({ level: "required", text: m.frequency ? `Timing "${m.frequency}" isn't clear — choose when to take it` : "When to take it isn't written" });
  if (!m.dosage) gaps.push({ level: "check", text: "Dose each time isn't written (e.g. 1 tablet)" });
  if (!m.strength) gaps.push({ level: "check", text: "Strength isn't written (e.g. 500 mg)" });
  for (const f of rev?.flags || []) {
    if (!COVERED.has(f.code) && f.severity !== "info") gaps.push({ level: f.severity === "high" ? "required" : "check", text: f.message });
  }
  if (m.duration_days == null && !fp.asNeeded) gaps.push({ level: "info", text: "Number of days isn't written" });
  if (!m.meal_relation || m.meal_relation === "any") gaps.push({ level: "info", text: "Before or after food isn't written" });
  return gaps;
}

function MissingInfoSummary({ medicines, items, onReview }: { medicines: any[]; items: ItemReview[]; onReview: (i: number) => void }) {
  const rows = medicines
    .map((m, i) => ({ i, m, gaps: m.include === false ? [] : medicineGaps(m, items.find((x) => x.index === i)) }))
    .filter((r) => r.gaps.length);
  const serious = rows.filter((r) => r.gaps.some((g) => g.level !== "info"));
  const minorOnly = rows.filter((r) => r.gaps.every((g) => g.level === "info"));
  const included = medicines.filter((m) => m.include !== false).length;
  if (!included) return null;
  if (!serious.length) {
    return (
      <div className="flex items-start gap-3 rounded-2xl bg-primary-50 px-4 py-3 text-[0.9rem] text-primary-800">
        <CircleCheck className="mt-0.5 h-5 w-5 shrink-0" />
        <div><b>Every medicine has a time, dose and strength.</b> Still compare each one with your paper before saving.
          {minorOnly.length > 0 && <span className="text-primary-800/80"> Days or food timing aren&apos;t written for {minorOnly.length} medicine{minorOnly.length > 1 ? "s" : ""}.</span>}</div>
      </div>
    );
  }
  const required = serious.filter((r) => r.gaps.some((g) => g.level === "required")).length;
  return (
    <section aria-labelledby="missing-title" className="rounded-2xl border border-warning/40 bg-warning-bg/50 p-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warning-ink" />
        <div className="min-w-0 flex-1">
          <h3 id="missing-title" className="font-semibold text-ink">{serious.length} of {included} medicines are missing details</h3>
          <p className="mt-0.5 text-[0.85rem] text-ink-soft">
            {required ? "Items in red must be fixed (or the medicine unticked) before saving. " : ""}Ask your doctor or pharmacist for anything not written on the prescription — please don&apos;t guess.
          </p>
          <ul className="mt-3 divide-y divide-warning/20 overflow-hidden rounded-xl bg-surface">
            {serious.map(({ i, m, gaps }) => (
              <li key={i} className="flex items-start gap-3 px-3 py-2.5">
                <div className="min-w-0 flex-1">
                  <div className="font-semibold text-ink">{m.name || `Medicine ${i + 1}`}</div>
                  <ul className="mt-1 space-y-0.5">
                    {gaps.filter((g) => g.level !== "info").map((g, k) => (
                      <li key={k} className={cn("flex items-start gap-1.5 text-[0.85rem]", g.level === "required" ? "text-danger-ink" : "text-warning-ink")}>
                        {g.level === "required" ? <CircleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" /> : <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />}
                        <span>{g.text}</span>
                      </li>
                    ))}
                    {gaps.some((g) => g.level === "info") && <li className="text-[0.8rem] text-muted">Also not written: {gaps.filter((g) => g.level === "info").map((g) => g.text.replace(" isn't written", "").toLowerCase()).join(", ")}</li>}
                  </ul>
                </div>
                <Button variant="outline" size="sm" onClick={() => onReview(i)}>Review</Button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
export function PrescriptionEditor({ data, setData, items, duplicates, options, setOptions }: { data: any; setData: (d: any) => void; items: ItemReview[]; duplicates: any[]; options: any; setOptions: (o: any) => void }) {
  const { lang, t } = useI18n();
  const upd = (i: number, patch: any) => setData({ ...data, medicines: data.medicines.map((m: any, j: number) => (j === i ? { ...m, ...patch } : m)) });
  const [focus, setFocus] = useState<number | null>(null);
  const review = (i: number) => {
    setFocus(i);
    document.getElementById(`med-${i}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => setFocus((f) => (f === i ? null : f)), 2500);
  };
  return (
    <div className="space-y-5">
      <MissingInfoSummary medicines={data.medicines} items={items} onReview={review} />
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Doctor"><Input value={data.doctor_name || ""} onChange={(e) => setData({ ...data, doctor_name: e.target.value })} /></Field>
        <Field label="Clinic / hospital"><Input value={data.clinic || ""} onChange={(e) => setData({ ...data, clinic: e.target.value })} /></Field>
        <Field label="Prescription date"><Input type="date" value={data.prescribed_date || ""} onChange={(e) => setData({ ...data, prescribed_date: e.target.value })} /></Field>
      </div>
      {data.medicines.length === 0 && <p className="rounded-xl bg-warning-bg px-4 py-3 text-sm text-warning-ink">No medicines could be read. If the prescription is unclear, please check with your pharmacist or doctor, or add medicines manually from the Medicines page.</p>}
      <div className="space-y-3">
        {data.medicines.map((m: any, i: number) => {
          const rev = items.find((x) => x.index === i);
          const fp = parseFrequency(m.frequency);
          const slots: string[] = m.slots ?? fp.slots;
          const included = m.include !== false;
          const needsSlots = included && !fp.asNeeded && slots.length === 0;
          const gaps = included ? medicineGaps(m, rev).filter((g) => g.level !== "info") : [];
          return (
            <div key={i} id={`med-${i}`} className={cn("scroll-mt-24 rounded-2xl border bg-surface p-4 transition-[opacity,box-shadow]", needsSlots ? "border-danger/50" : "border-line", !included && "opacity-55", focus === i && "ring-4 ring-warning/50")}>
              <div className="flex items-start gap-3">
                <Checkbox checked={included} onCheckedChange={(v) => upd(i, { include: !!v })} aria-label={`Include ${m.name}`} className="mt-3" />
                <div className="min-w-0 flex-1 space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Input className="h-11 max-w-xs font-semibold" aria-label="Medicine name" value={m.name} onChange={(e) => upd(i, { name: e.target.value })} />
                    {m.generic_name && m.generic_name !== m.name && <Badge variant="outline">{m.generic_name}{m.generic_source === "dictionary" ? " (from brand)" : ""}</Badge>}
                    {m.form && <Badge>{m.form}</Badge>}
                    {rev && <ConfidenceChip value={rev.confidence} />}
                    {gaps.length > 0 && (
                      <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.72rem] font-semibold", gaps.some((g) => g.level === "required") ? "bg-danger-bg text-danger-ink" : "bg-warning-bg text-warning-ink")}>
                        <AlertTriangle className="h-3 w-3" /> {gaps.length} missing
                      </span>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    <Field label="Strength"><Input value={m.strength || ""} onChange={(e) => upd(i, { strength: e.target.value })} placeholder="e.g. 500mg" /></Field>
                    <Field label="Dose each time"><Input value={m.dosage || ""} onChange={(e) => upd(i, { dosage: e.target.value })} placeholder="e.g. 1 tablet" /></Field>
                    <Field label="How often (as written)"><Input value={m.frequency || ""} onChange={(e) => upd(i, { frequency: e.target.value, slots: undefined })} placeholder="e.g. 1-0-1" /></Field>
                    <Field label="Duration (days)"><Input type="number" min={1} value={m.duration_days ?? ""} onChange={(e) => upd(i, { duration_days: e.target.value ? parseInt(e.target.value) : null })} /></Field>
                  </div>
                  <div className="grid gap-3 md:grid-cols-[1fr_1.4fr]">
                    <Field label="Food timing">
                      <NativeSelect value={m.meal_relation || "any"} onChange={(e) => upd(i, { meal_relation: e.target.value })}>
                        {Object.entries(MEAL_REL).map(([k, v]) => <option key={k} value={k}>{v[lang]}</option>)}
                      </NativeSelect>
                    </Field>
                    <Field label={fp.nonDaily ? "Not daily — no automatic reminder" : fp.asNeeded ? "Only when needed — no fixed reminder" : "When to take"} error={needsSlots ? "Choose the times written on your prescription (or untick this medicine)." : null}>
                      <div className="flex flex-wrap gap-2">
                        {SLOTS.map((s) => {
                          const Icon = SLOT_ICONS[s];
                          const on = slots.includes(s);
                          return (
                            <button key={s} type="button" disabled={fp.asNeeded} aria-pressed={on}
                              onClick={() => upd(i, { slots: on ? slots.filter((x) => x !== s) : [...slots, s] })}
                              className={cn("inline-flex h-11 items-center gap-1.5 rounded-xl border px-3 text-sm font-medium transition-colors disabled:opacity-40", on ? "border-primary bg-primary text-white" : "border-line-strong bg-surface text-ink-soft hover:bg-muted-bg")}>
                              <Icon className="h-4 w-4" /> {t(s.charAt(0).toUpperCase() + s.slice(1))}
                            </button>
                          );
                        })}
                      </div>
                    </Field>
                  </div>
                  <div className="grid gap-3 md:grid-cols-[1.4fr_1fr]">
                    <Field label="Instructions"><Input value={m.instructions || ""} onChange={(e) => upd(i, { instructions: e.target.value })} placeholder="Optional" /></Field>
                    <Field label="Tablets you have (for refill reminders)"><Input type="number" min={0} value={m.stock_count ?? ""} onChange={(e) => upd(i, { stock_count: e.target.value ? parseInt(e.target.value) : null })} placeholder="Optional" /></Field>
                  </div>
                  {rev?.flags?.length ? <FlagList flags={rev.flags} /> : null}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      {(data.follow_up_date || duplicates.length > 0) && (
        <div className="space-y-3 rounded-2xl border border-line bg-background p-4">
          {data.follow_up_date && (
            <label className="flex items-center gap-3 text-sm">
              <Checkbox checked={!!options.create_follow_up} onCheckedChange={(v) => setOptions({ ...options, create_follow_up: !!v })} />
              <span>Add the follow-up visit on <b>{data.follow_up_date}</b> to my appointments</span>
            </label>
          )}
          {duplicates.length > 0 && (
            <label className="flex items-center gap-3 text-sm">
              <Checkbox checked={!!options.replace_duplicates} onCheckedChange={(v) => setOptions({ ...options, replace_duplicates: !!v })} />
              <span>This looks like a renewed prescription — replace my existing entries for {duplicates.map((d) => d.existing).join(", ")}</span>
            </label>
          )}
        </div>
      )}
    </div>
  );
}

/* ---------- Diet / consultation / appointment ---------- */
const RESTRICTIONS: Record<string, string> = { low_sodium: "Low salt", low_sugar: "Low sugar", low_fat: "Low fat", high_fibre: "High fibre", protein_restricted: "Protein restricted", low_potassium: "Low potassium", fluid_restricted: "Fluid restricted", low_purine: "Low purine", high_protein: "Higher protein" };

function ListEditor({ label, values, onChange, items }: { label: string; values: string[]; onChange: (v: string[]) => void; items?: ItemReview[] }) {
  return (
    <Field label={label}>
      <div className="space-y-2">
        {values.map((v, i) => {
          const rev = items?.find((x) => x.index === i);
          return (
            <div key={i}>
              <div className="flex gap-2">
                <Input value={v} onChange={(e) => onChange(values.map((x, j) => (j === i ? e.target.value : x)))} />
                <Button variant="ghost" size="icon" aria-label="Remove" onClick={() => onChange(values.filter((_, j) => j !== i))}><Trash2 /></Button>
              </div>
              {rev?.flags?.length ? <FlagList flags={rev.flags} className="mt-1.5" /> : null}
            </div>
          );
        })}
        <Button variant="outline" size="sm" onClick={() => onChange([...values, ""])}><Plus /> Add</Button>
      </div>
    </Field>
  );
}

function RestrictionPicker({ value, onChange }: { value: string[]; onChange: (v: string[]) => void }) {
  return (
    <Field label="Dietary rules to follow" hint="These become hard rules in your meal plan.">
      <div className="flex flex-wrap gap-2">
        {Object.entries(RESTRICTIONS).map(([k, label]) => {
          const on = value.includes(k);
          return (
            <button key={k} type="button" aria-pressed={on} onClick={() => onChange(on ? value.filter((x) => x !== k) : [...value, k])}
              className={cn("h-10 rounded-xl border px-3 text-sm font-medium", on ? "border-primary bg-primary-100 text-primary-800" : "border-line-strong text-ink-soft hover:bg-muted-bg")}>{label}</button>
          );
        })}
      </div>
    </Field>
  );
}

export function DietEditor({ data, setData, items }: { data: any; setData: (d: any) => void; items: ItemReview[] }) {
  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Doctor"><Input value={data.doctor_name || ""} onChange={(e) => setData({ ...data, doctor_name: e.target.value })} /></Field>
        <Field label="Date"><Input type="date" value={data.advice_date || ""} onChange={(e) => setData({ ...data, advice_date: e.target.value })} /></Field>
      </div>
      <ListEditor label="Doctor's instructions (as written)" values={data.instructions} onChange={(v) => setData({ ...data, instructions: v })} items={items} />
      <RestrictionPicker value={data.restrictions} onChange={(v) => setData({ ...data, restrictions: v })} />
    </div>
  );
}

export function ConsultationEditor({ data, setData, items, options, setOptions }: { data: any; setData: (d: any) => void; items: ItemReview[]; options: any; setOptions: (o: any) => void }) {
  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Doctor"><Input value={data.doctor_name || ""} onChange={(e) => setData({ ...data, doctor_name: e.target.value })} /></Field>
        <Field label="Specialization"><Input value={data.specialization || ""} onChange={(e) => setData({ ...data, specialization: e.target.value })} /></Field>
        <Field label="Clinic / hospital"><Input value={data.clinic || ""} onChange={(e) => setData({ ...data, clinic: e.target.value })} /></Field>
        <Field label="Visit date"><Input type="date" value={data.visit_date || ""} onChange={(e) => setData({ ...data, visit_date: e.target.value })} /></Field>
      </div>
      <Field label="Summary (as written)"><Textarea value={data.summary || ""} onChange={(e) => setData({ ...data, summary: e.target.value })} /></Field>
      <ListEditor label="Advice" values={data.advice} onChange={(v) => setData({ ...data, advice: v })} items={items} />
      <ListEditor label="Diet instructions" values={data.diet_instructions} onChange={(v) => setData({ ...data, diet_instructions: v })} />
      <RestrictionPicker value={data.restrictions} onChange={(v) => setData({ ...data, restrictions: v })} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Follow-up date"><Input type="date" value={data.follow_up_date || ""} onChange={(e) => setData({ ...data, follow_up_date: e.target.value })} /></Field>
        {data.follow_up_date && (
          <label className="flex items-center gap-3 self-end pb-3 text-sm"><Checkbox checked={!!options.create_follow_up} onCheckedChange={(v) => setOptions({ ...options, create_follow_up: !!v })} /> Add follow-up to my appointments</label>
        )}
      </div>
    </div>
  );
}

export function AppointmentEditor({ data, setData }: { data: any; setData: (d: any) => void }) {
  const f = (k: string, label: string, type = "text") => (
    <Field label={label}><Input type={type} value={data[k] || ""} onChange={(e) => setData({ ...data, [k]: e.target.value })} /></Field>
  );
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {f("doctor_name", "Doctor")}{f("specialization", "Specialization")}{f("clinic", "Clinic / hospital")}{f("phone", "Phone")}
      {f("date", "Date", "date")}{f("time", "Time", "time")}
      <div className="sm:col-span-2">{f("address", "Address")}</div>
      <div className="sm:col-span-2"><Field label="Notes"><Textarea value={data.notes || ""} onChange={(e) => setData({ ...data, notes: e.target.value })} /></Field></div>
    </div>
  );
}
