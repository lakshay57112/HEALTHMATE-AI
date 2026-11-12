"use client";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Camera, CalendarClock, FileText, FileUp, FlaskConical, ImageIcon, Loader2, NotebookPen, Pill, Salad, ScanLine, ShieldCheck, Sparkles, Stethoscope, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, Progress } from "@/components/ui/primitives";
import { api, uploadFile, useApi } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { DOC_TYPES, cn } from "@/lib/utils";

const TYPE_CARDS = [
  { value: "auto", icon: Sparkles, hint: "We'll figure it out" },
  { value: "prescription", icon: Pill, hint: "Medicines & doses" },
  { value: "lab_report", icon: FlaskConical, hint: "Blood & lab tests" },
  { value: "consultation_note", icon: Stethoscope, hint: "Visit summary" },
  { value: "diet_advice", icon: Salad, hint: "What to eat/avoid" },
  { value: "appointment", icon: CalendarClock, hint: "Booking slip" },
];
const ACCEPT = "application/pdf,image/jpeg,image/png";
const MAX_MB = 15;

export function UploadPanel({ defaultType = "auto", lockType = false }: { defaultType?: string; lockType?: boolean }) {
  const { lang } = useI18n();
  const router = useRouter();
  const [type, setType] = useState(defaultType);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const cameraRef = useRef<HTMLInputElement>(null);
  const samples = useApi<{ items: { key: string; filename: string; type: string }[] }>("/documents/samples");
  const [sampleBusy, setSampleBusy] = useState<string | null>(null);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const pick = useCallback((f: File | undefined | null) => {
    if (!f) return;
    if (!ACCEPT.split(",").includes(f.type)) return toast.error("Please choose a PDF, JPG or PNG file.");
    if (f.size > MAX_MB * 1024 * 1024) return toast.error(`File is larger than ${MAX_MB} MB.`);
    setFile(f);
    setPreview(f.type.startsWith("image/") ? URL.createObjectURL(f) : null);
  }, []);

  const submit = async () => {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    fd.append("declared_type", type);
    setProgress(0);
    try {
      const d = await uploadFile("/documents", fd, setProgress);
      router.push(`/app/documents/${d.document.id}`);
    } catch (e: any) {
      toast.error(e.message);
      setProgress(null);
    }
  };

  const trySample = async (key: string) => {
    setSampleBusy(key);
    try {
      const d = await api(`/documents/samples/${key}`, { method: "POST" });
      router.push(`/app/documents/${d.document.id}`);
    } catch (e: any) {
      toast.error(e.message);
      setSampleBusy(null);
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <div className="space-y-6">
        {!lockType && (
          <div>
            <div className="mb-3 text-sm font-medium text-ink-soft">What are you uploading?</div>
            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
              {TYPE_CARDS.map((c) => (
                <button key={c.value} type="button" onClick={() => setType(c.value)} aria-pressed={type === c.value}
                  className={cn("flex items-center gap-3 rounded-2xl border bg-surface p-3.5 text-left transition-all hover:border-primary-300", type === c.value ? "border-primary ring-4 ring-primary/10" : "border-line")}>
                  <span className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl", type === c.value ? "bg-primary text-white" : "bg-muted-bg text-muted")}><c.icon className="h-5 w-5" /></span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-semibold">{DOC_TYPES[c.value][lang]}</span>
                    <span className="block truncate text-[0.78rem] text-muted">{c.hint}</span>
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        <Card
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files?.[0]); }}
          className={cn("border-2 border-dashed p-0 transition-colors", drag ? "border-primary bg-primary-50" : "border-line-strong")}
        >
          {!file ? (
            <div className="flex flex-col items-center px-6 py-12 text-center">
              <span className="mb-4 flex h-16 w-16 items-center justify-center rounded-3xl bg-secondary text-primary"><FileUp className="h-7 w-7" /></span>
              <h3 className="text-lg font-semibold">Drop your document here</h3>
              <p className="mt-1 text-sm text-muted">PDF, JPG or PNG · up to {MAX_MB} MB</p>
              <div className="mt-6 flex flex-col gap-2.5 sm:flex-row">
                <Button size="lg" className="h-12" onClick={() => inputRef.current?.click()}><FileText /> Choose file</Button>
                <Button size="lg" variant="outline" className="h-12" onClick={() => cameraRef.current?.click()}><Camera /> Take a photo</Button>
              </div>
              <input ref={inputRef} type="file" accept={ACCEPT} className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
              <input ref={cameraRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
            </div>
          ) : (
            <div className="p-5">
              <div className="flex items-start gap-4">
                <div className="flex h-28 w-24 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-line bg-background">
                  {preview ? <img src={preview} alt="Preview" className="h-full w-full object-cover" /> : <FileText className="h-8 w-8 text-muted" />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-semibold">{file.name}</div>
                  <div className="text-sm text-muted">{(file.size / 1024).toFixed(0)} KB · {DOC_TYPES[type][lang]}</div>
                  {progress !== null && (
                    <div className="mt-4 space-y-1.5">
                      <Progress value={progress} />
                      <div className="flex items-center gap-1.5 text-[0.82rem] text-muted">
                        {progress < 100 ? <>Uploading… {progress}%</> : <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Starting analysis…</>}
                      </div>
                    </div>
                  )}
                </div>
                {progress === null && <button onClick={() => { setFile(null); setPreview(null); }} className="rounded-lg p-2 text-muted hover:bg-muted-bg" aria-label="Remove file"><X className="h-5 w-5" /></button>}
              </div>
              <Button size="lg" className="mt-5 h-12 w-full" onClick={submit} loading={progress !== null}><ScanLine /> Read this document</Button>
            </div>
          )}
        </Card>

        <div className="flex items-start gap-2.5 rounded-xl bg-muted-bg px-4 py-3 text-[0.85rem] text-ink-soft">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
          Your file is encrypted before it is stored. Nothing is added to your medicines or records until you check and confirm it.
        </div>
      </div>

      <aside className="space-y-4">
        <Card className="p-5">
          <div className="flex items-center gap-2 font-semibold"><ImageIcon className="h-4 w-4 text-primary" /> Tips for a clear photo</div>
          <ul className="mt-3 space-y-2 text-sm text-muted">
            <li>• Place the paper on a flat, dark surface</li>
            <li>• Good light, no shadows or glare</li>
            <li>• Keep the whole page inside the frame</li>
            <li>• Handwritten prescriptions may need more checking</li>
          </ul>
        </Card>
        <Card className="p-5">
          <div className="flex items-center gap-2 font-semibold"><NotebookPen className="h-4 w-4 text-primary" /> No document handy?</div>
          <p className="mt-1 text-sm text-muted">Try a sample (fictional patient) to see how it works.</p>
          <div className="mt-3 space-y-1.5">
            {(samples.data?.items || []).filter((s) => !lockType || s.type === defaultType || (defaultType === "prescription" && s.key.startsWith("prescription"))).map((s) => (
              <button key={s.key} onClick={() => trySample(s.key)} disabled={!!sampleBusy}
                className="flex w-full items-center justify-between gap-2 rounded-xl border border-line px-3 py-2.5 text-left text-sm hover:border-primary-300 hover:bg-primary-50 disabled:opacity-60">
                <span className="truncate">{s.key === "injection_test" ? "Security test (hidden instructions)" : s.key === "prescription_photo" ? "Prescription photo (OCR)" : DOC_TYPES[s.type]?.[lang] || s.key}</span>
                {sampleBusy === s.key ? <Loader2 className="h-4 w-4 animate-spin text-primary" /> : <span className="text-[0.78rem] text-primary">Try</span>}
              </button>
            ))}
          </div>
        </Card>
      </aside>
    </div>
  );
}
