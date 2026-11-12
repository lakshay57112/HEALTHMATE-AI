"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Check, CheckCircle2, ChevronDown, Circle, FileText, Loader2, RefreshCw, ShieldAlert, ShieldCheck, Trash2, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import { ErrorState, PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Badge, Card, Checkbox, NativeSelect, Progress, Skeleton } from "@/components/ui/primitives";
import { AppointmentEditor, ConsultationEditor, DietEditor, FlagList, LabEditor, PrescriptionEditor, parseFrequency, type Flag } from "@/components/verify";
import { api, useApi } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { DOC_TYPES, cn, fmtDateTime } from "@/lib/utils";

const STEPS = ["intake", "ocr", "injection_guard", "classifier", "extractor", "review", "ready"];
const STEP_LABEL: Record<string, string> = { intake: "Checking your file", ocr: "Reading the text", injection_guard: "Security check", classifier: "Detecting document type", extractor: "Extracting information", review: "Double-checking every value", ready: "Ready for your review" };
const EMPTY: Record<string, any> = {
  lab_report: { title: "", lab_name: "", report_date: "", tests: [] },
  prescription: { doctor_name: "", clinic: "", prescribed_date: "", medicines: [] },
  diet_advice: { doctor_name: "", advice_date: "", instructions: [], restrictions: [] },
  appointment: { doctor_name: "", date: "", time: "" },
  consultation_note: { doctor_name: "", visit_date: "", summary: "", advice: [], diet_instructions: [], restrictions: [] },
  other: {},
};

function Preview({ doc }: { doc: any }) {
  const src = `/api/documents/${doc.id}/file`;
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-3 text-sm">
        <span className="flex min-w-0 items-center gap-2 font-medium"><FileText className="h-4 w-4 shrink-0 text-muted" /><span className="truncate">{doc.filename}</span></span>
        <a href={src} target="_blank" rel="noreferrer" className="shrink-0 text-primary hover:underline">Open</a>
      </div>
      <div className="h-[420px] overflow-auto bg-background lg:h-[560px]">
        <img src={`/api/documents/${doc.id}/preview`} alt={`Preview of ${doc.filename}`} className="h-full w-full object-contain object-top" />
      </div>
    </Card>
  );
}

function Steps({ steps, compact }: { steps: any[]; compact?: boolean }) {
  const byName = Object.fromEntries((steps || []).map((s) => [s.step, s]));
  return (
    <ol className="space-y-3">
      {STEPS.map((name) => {
        const s = byName[name];
        const state = !s ? "pending" : s.status === "running" ? "running" : s.status;
        return (
          <li key={name} className="flex items-start gap-3">
            <span className="mt-0.5">
              {state === "running" ? <Loader2 className="h-5 w-5 animate-spin text-primary" /> : state === "pending" ? <Circle className="h-5 w-5 text-line-strong" /> :
                state === "warning" ? <TriangleAlert className="h-5 w-5 text-warning" /> : <CheckCircle2 className="h-5 w-5 text-primary" />}
            </span>
            <div className="min-w-0">
              <div className={cn("text-[0.95rem] font-medium", state === "pending" && "text-muted")}>{STEP_LABEL[name]}</div>
              {!compact && s?.detail && <div className="text-[0.82rem] text-muted">{s.detail}{s.ms ? ` · ${s.ms} ms` : ""}</div>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export default function DocumentPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { lang } = useI18n();
  const { data, error, loading, reload } = useApi<{ document: any }>(`/documents/${id}`);
  const doc = data?.document;
  const processing = doc && ["uploaded", "processing"].includes(doc.status);

  useEffect(() => {
    if (!processing) return;
    const tmr = setTimeout(reload, 1000);
    return () => clearTimeout(tmr);
  }, [processing, data, reload]);

  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (loading || !doc) return <div className="space-y-4"><Skeleton className="h-10 w-72" /><Skeleton className="h-96" /></div>;

  if (processing) {
    const done = (doc.steps || []).filter((s: any) => s.status !== "running").length;
    return (
      <>
        <PageHeader eyebrow="Reading your document" title={doc.filename} description="This usually takes a few seconds. You can leave this page — we'll keep working." back="/app/documents" />
        <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
          <Card className="p-6">
            <Progress value={(done / STEPS.length) * 100} className="mb-6" />
            <Steps steps={doc.steps} />
          </Card>
          <Preview doc={doc} />
        </div>
      </>
    );
  }
  if (doc.status === "failed") {
    return (
      <>
        <PageHeader title={doc.filename} back="/app/documents" />
        <ErrorState message={doc.error || "We couldn't process this document."} onRetry={async () => { await api(`/documents/${id}/reprocess`, { method: "POST" }); reload(); }} />
      </>
    );
  }
  if (doc.status === "verified" || doc.status === "rejected") return <DoneView doc={doc} />;
  return <VerifyView doc={doc} onReload={reload} onDone={() => reload()} router={router} lang={lang} />;
}

function VerifyView({ doc, onReload, onDone, router, lang }: { doc: any; onReload: () => void; onDone: () => void; router: any; lang: "en" | "hi" }) {
  const ext = doc.extraction || {};
  const review = ext.review || { items: [], flags: [], overall_confidence: 0 };
  const [type, setType] = useState<string>(ext.type || doc.detected_type || "other");
  const [form, setForm] = useState<any>(() => structuredClone(ext.data && Object.keys(ext.data).length ? ext.data : EMPTY[ext.type || "other"] || {}));
  const [options, setOptions] = useState<any>({ create_follow_up: true, replace_duplicates: (review.duplicates || []).length > 0 });
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [showText, setShowText] = useState(false);
  const docFlags: Flag[] = review.flags || [];
  const highCount = docFlags.filter((f) => f.severity === "high").length + (review.items || []).reduce((n: number, i: any) => n + i.flags.filter((f: Flag) => f.severity === "high").length, 0);
  const injection = docFlags.some((f) => f.code === "possible_injection");

  const missingSlots = useMemo(() => type === "prescription" && (form.medicines || []).some((m: any) => m.include !== false && !parseFrequency(m.frequency).asNeeded && (m.slots ?? parseFrequency(m.frequency).slots).length === 0), [form, type]);

  const changeType = async (t: string) => {
    if (t === type) return;
    if (!confirm(`Re-read this document as "${DOC_TYPES[t].en}"?`)) return;
    await api(`/documents/${doc.id}/reprocess?declared_type=${t}`, { method: "POST" });
    setType(t);
    onReload();
  };

  const confirmSave = async () => {
    setBusy(true);
    try {
      const payload = { type, data: type === "prescription" ? { ...form, medicines: form.medicines.map((m: any) => ({ ...m, slots: m.slots ?? parseFrequency(m.frequency).slots })) } : form, options };
      const res = await api(`/documents/${doc.id}/confirm`, { method: "POST", json: payload });
      toast.success("Saved. Your records have been updated.");
      const c = res.result.created || {};
      if (c.report_id) router.push(`/app/reports/${c.report_id}`);
      else if (c.prescription_id) router.push(`/app/medicines/schedule`);
      else if (type === "diet_advice") router.push("/app/nutrition");
      else if (c.appointment_id) router.push("/app/appointments");
      else onDone();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    if (!confirm("Discard this document? It will be kept in history as rejected and nothing will be saved.")) return;
    await api(`/documents/${doc.id}/reject`, { method: "POST" });
    router.push("/app/documents");
  };

  return (
    <>
      <PageHeader eyebrow="Step 2 of 2 · Check and confirm" title="Is this information correct?" description="Please compare each value with your paper. Edit anything that looks wrong. Nothing is saved until you confirm." back="/app/documents" />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.3fr)]">
        <div className="space-y-4 lg:sticky lg:top-24 lg:self-start">
          <Preview doc={doc} />
          <Card className="p-4">
            <button onClick={() => setShowText((s) => !s)} className="flex w-full items-center justify-between text-sm font-medium">
              Text we read ({doc.ocr_method?.replace("_", " ") || "—"}) <ChevronDown className={cn("h-4 w-4 transition-transform", showText && "rotate-180")} />
            </button>
            {showText && <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap rounded-xl bg-background p-3 font-mono text-[0.75rem] text-ink-soft">{doc.ocr_text_preview || "No text could be read."}</pre>}
          </Card>
          <Card className="p-4"><div className="mb-3 text-sm font-medium">How we processed it</div><Steps steps={doc.steps} compact /></Card>
        </div>

        <div className="space-y-5">
          <Card className="p-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                {injection ? <ShieldAlert className="h-9 w-9 text-danger" /> : <ShieldCheck className="h-9 w-9 text-primary" />}
                <div>
                  <div className="font-semibold">Read with {Math.round((review.overall_confidence || 0) * 100)}% confidence</div>
                  <div className="text-sm text-muted">{highCount ? `${highCount} item(s) need your attention` : "Every value was found in your document"} · {doc.extractor === "rules-v1" ? "Rule-based reader (offline demo)" : doc.extractor ? `AI reader · ${doc.extractor}` : ""}</div>
                </div>
              </div>
              <div className="w-full sm:w-56">
                <NativeSelect value={type} onChange={(e) => changeType(e.target.value)} aria-label="Document type">
                  {Object.entries(DOC_TYPES).filter(([k]) => k !== "auto").map(([k, v]) => <option key={k} value={k}>{v[lang]}</option>)}
                </NativeSelect>
              </div>
            </div>
            <Progress value={(review.overall_confidence || 0) * 100} className="mt-4" indicatorClassName={review.overall_confidence < 0.7 ? "bg-danger" : review.overall_confidence < 0.85 ? "bg-warning" : "bg-primary"} />
            {docFlags.length > 0 && <FlagList flags={docFlags} className="mt-4" />}
          </Card>

          <Card className="p-5">
            {type === "lab_report" && <LabEditor data={{ tests: [], ...form }} setData={setForm} items={review.items} />}
            {type === "prescription" && <PrescriptionEditor data={{ medicines: [], ...form }} setData={setForm} items={review.items} duplicates={review.duplicates || []} options={options} setOptions={setOptions} />}
            {type === "diet_advice" && <DietEditor data={{ instructions: [], restrictions: [], ...form }} setData={setForm} items={review.items} />}
            {type === "consultation_note" && <ConsultationEditor data={{ advice: [], diet_instructions: [], restrictions: [], ...form }} setData={setForm} items={review.items} options={options} setOptions={setOptions} />}
            {type === "appointment" && <AppointmentEditor data={form} setData={setForm} />}
            {type === "other" && <p className="text-sm text-muted">This document will be stored in your health history. No structured information will be added.</p>}
          </Card>

          <Card className="sticky bottom-20 z-10 p-5 shadow-lift lg:bottom-4">
            <label className="flex items-start gap-3 text-[0.95rem]">
              <Checkbox checked={ack} onCheckedChange={(v) => setAck(!!v)} className="mt-0.5" />
              <span>I have checked this information against my document.{type === "prescription" && " If anything is unclear, I will confirm with my pharmacist or doctor."}</span>
            </label>
            {missingSlots && <p className="mt-2 text-sm text-danger-ink">Choose when to take each ticked medicine before saving.</p>}
            <div className="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
              <Button variant="ghost" onClick={reject}><Trash2 /> Discard</Button>
              <Button size="lg" className="h-12" disabled={!ack || missingSlots} loading={busy} onClick={confirmSave}><Check /> Confirm and save</Button>
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}

function DoneView({ doc }: { doc: any }) {
  const verified = doc.status === "verified";
  const t = doc.detected_type;
  const link = t === "lab_report" ? "/app/reports" : t === "prescription" ? "/app/medicines" : t === "diet_advice" ? "/app/nutrition" : t === "appointment" || t === "consultation_note" ? "/app/appointments" : "/app/history";
  return (
    <>
      <PageHeader eyebrow={verified ? "Verified" : "Discarded"} title={doc.filename} description={verified ? `Confirmed ${fmtDateTime(doc.verified_at)}. The information has been added to your records.` : "This document was discarded. Nothing was saved from it."} back="/app/documents"
        actions={verified ? <Button asChild><Link href={link}>Go to {DOC_TYPES[t]?.en || "records"} <ArrowRight /></Link></Button> : undefined} />
      <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <Preview doc={doc} />
        <Card className="p-5">
          <div className="mb-3 flex items-center gap-2"><Badge variant={verified ? "success" : "default"}>{verified ? "Verified by you" : "Rejected"}</Badge><Badge variant="outline">{DOC_TYPES[t]?.en || t}</Badge></div>
          <Steps steps={doc.steps} />
          <Button variant="ghost" size="sm" className="mt-4" onClick={async () => { if (confirm("Delete this document file and its search index? Records already created stay.")) { await api(`/documents/${doc.id}`, { method: "DELETE" }); window.location.href = "/app/documents"; } }}>
            <Trash2 /> Delete file
          </Button>
        </Card>
      </div>
    </>
  );
}

const _r = RefreshCw;
