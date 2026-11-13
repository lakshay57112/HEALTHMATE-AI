"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import {
  Bot, CalendarClock, Check, ChevronDown, FileText, History, Loader2, Mic, MicOff, Plus, Send, ShieldAlert, ShieldCheck, Siren, Sparkles, Square, Trash2, Volume2, Wrench, X,
} from "lucide-react";
import { toast } from "sonner";
import { ParameterTrend } from "@/components/charts";
import { StatusPill } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Badge, Card } from "@/components/ui/primitives";
import { api, streamChat, useApi, type AgentEvent } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn, fmtTime } from "@/lib/utils";
import { recognitionSupported, shortForSpeech, speak, startRecognition, stopSpeaking, useSpeaking } from "@/lib/voice";

type ToolRun = { id: string; name: string; args?: string; ok?: boolean; untrusted?: boolean; done?: boolean };
type Msg = { id: string; role: "user" | "assistant"; content: string; tools?: ToolRun[]; cards?: any[]; guardrails?: any[]; citations?: any[]; proposals?: any[]; mode?: string; streaming?: boolean; error?: string };

const SUGGESTIONS = [
  "What medicines are scheduled today?", "What does my blood report mean?", "Has my HbA1c improved?", "What did my doctor recommend for my diet?",
  "When is my next appointment?", "मेरी कोलेस्ट्रॉल रिपोर्ट हिंदी में समझाइए", "Log my BP 130/84", "How many doses did I miss this week?",
];
const TOOL_LABEL: Record<string, string> = {
  get_patient_profile: "Checked your profile", get_todays_medicines: "Looked up today's medicines", get_medicine_list: "Looked up your medicines", get_adherence: "Calculated adherence",
  get_upcoming_appointments: "Checked appointments", get_latest_report_summary: "Read your latest verified report", get_parameter_history: "Compared past reports",
  get_diet_instructions: "Read your doctor's diet advice", get_health_measurements: "Looked up readings", search_health_records: "Searched your documents",
  explain_medical_term: "Looked up a medical term", propose_appointment: "Prepared an appointment", propose_measurement_log: "Prepared a reading", remember_preference: "Saved a preference",
};

function UICard({ card }: { card: any }) {
  const d = card.data;
  if (card.type === "medicine_list" && d.doses?.length) {
    return (
      <Card className="divide-y divide-line">
        {d.doses.map((x: any, i: number) => (
          <div key={i} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
            <span><span className="font-medium tnum">{fmtTime(x.effective_time)}</span> · {x.name} <span className="text-muted">{x.strength}</span></span>
            <StatusPill status={x.status} />
          </div>
        ))}
      </Card>
    );
  }
  if (card.type === "lab_summary" && d.report) {
    const ab = d.report.parameters.filter((p: any) => p.status === "high" || p.status === "low");
    return (
      <Link href={`/app/reports/${d.report.id}`}>
        <Card className="p-4 transition-shadow hover:shadow-soft">
          <div className="flex items-center gap-2 text-sm font-semibold"><FileText className="h-4 w-4 text-primary" />{d.report.title} <span className="font-normal text-muted">· {d.report.date}</span>{d.report.is_sample && <Badge variant="info">sample</Badge>}</div>
          <div className="mt-2 flex flex-wrap gap-1.5">{ab.slice(0, 6).map((p: any) => <Badge key={p.name} variant={p.status === "high" ? "danger" : "warning"}>{p.name}: {p.value} {p.unit}</Badge>)}</div>
        </Card>
      </Link>
    );
  }
  if (card.type === "trend" && d.history?.filter((h: any) => h.value != null).length > 1) {
    return <Card className="p-3"><div className="px-1 pb-1 text-sm font-semibold">{d.label}</div><ParameterTrend history={d.history} height={160} /></Card>;
  }
  if (card.type === "appointments" && d.appointments?.length) {
    const a = d.appointments[0];
    return <Card className="flex items-center gap-3 p-4 text-sm"><CalendarClock className="h-5 w-5 text-primary" /><div><div className="font-semibold">{a.doctor}</div><div className="text-muted">{a.when}{a.clinic ? ` · ${a.clinic}` : ""}</div></div></Card>;
  }
  if (card.type === "emergency") {
    return (
      <Card className="border-danger/40 bg-danger-bg p-4">
        <div className="flex items-center gap-2 font-semibold text-danger-ink"><Siren className="h-5 w-5" /> Get help now</div>
        <div className="mt-3 flex flex-wrap gap-2">{d.numbers.map((n: any) => <Button key={n.number} asChild variant="danger" size="lg"><a href={`tel:${n.number}`}>{n.label}: {n.number}</a></Button>)}</div>
      </Card>
    );
  }
  return null;
}

function Proposal({ p, onDecide }: { p: any; onDecide: (id: string, status: string) => void }) {
  const [busy, setBusy] = useState(false);
  const decide = async (decision: "approve" | "reject") => {
    setBusy(true);
    try {
      const r = await api(`/assistant/proposals/${p.id}/${decision}`, { method: "POST" });
      onDecide(p.id, r.status);
      toast.success(decision === "approve" ? "Saved" : "Dismissed");
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card className="border-primary-200 bg-primary-50/60 p-4">
      <div className="eyebrow text-primary">Needs your approval</div>
      <div className="mt-1 font-medium">{p.summary}</div>
      {p.status && p.status !== "pending" ? (
        <Badge className="mt-3" variant={p.status === "approved" ? "success" : "default"}>{p.status}</Badge>
      ) : (
        <div className="mt-3 flex gap-2"><Button size="sm" loading={busy} onClick={() => decide("approve")}><Check /> Approve</Button><Button size="sm" variant="outline" disabled={busy} onClick={() => decide("reject")}><X /> Dismiss</Button></div>
      )}
    </Card>
  );
}

function AssistantInner() {
  const { lang } = useI18n();
  const params = useSearchParams();
  const status = useApi<any>("/assistant/status");
  const sessions = useApi<{ items: any[] }>("/assistant/sessions");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const speaking = useSpeaking();
  const [readingId, setReadingId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const recRef = useRef<any>(null);
  const asked = useRef(false);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [msgs]);
  useEffect(() => {
    const q = params.get("q");
    if (q && !asked.current) {
      asked.current = true;
      send(q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  const loadSession = async (id: string) => {
    const d = await api(`/assistant/sessions/${id}/messages`);
    setSessionId(id);
    setMsgs(d.items.map((m: any) => ({ id: m.id, role: m.role, content: m.content, citations: m.meta?.citations, proposals: m.meta?.proposals, mode: m.meta?.mode,
      tools: (m.meta?.tools || []).map((t: any, i: number) => ({ id: String(i), name: t.tool, ok: t.ok, done: true })), guardrails: m.meta?.guardrails })));
    setShowHistory(false);
  };

  const send = async (text?: string) => {
    const message = (text ?? input).trim();
    if (!message || busy) return;
    setInput("");
    setBusy(true);
    const sid = sessionId || crypto.randomUUID();
    if (!sessionId) setSessionId(sid);
    const aid = crypto.randomUUID();
    setMsgs((m) => [...m, { id: crypto.randomUUID(), role: "user", content: message }, { id: aid, role: "assistant", content: "", tools: [], cards: [], guardrails: [], streaming: true }]);
    const patch = (fn: (m: Msg) => Msg) => setMsgs((all) => all.map((m) => (m.id === aid ? fn(m) : m)));
    try {
      await streamChat(message, sid, (e: AgentEvent) => {
        switch (e.type) {
          case "RUN_STARTED": patch((m) => ({ ...m, mode: e.mode })); break;
          case "TOOL_CALL_START": patch((m) => ({ ...m, tools: [...(m.tools || []), { id: e.toolCallId, name: e.toolCallName }] })); break;
          case "TOOL_CALL_ARGS": patch((m) => ({ ...m, tools: m.tools?.map((t) => (t.id === e.toolCallId ? { ...t, args: e.delta } : t)) })); break;
          case "TOOL_CALL_RESULT": patch((m) => ({ ...m, tools: m.tools?.map((t) => (t.id === e.toolCallId ? { ...t, ok: e.ok, untrusted: e.untrusted, done: true } : t)) })); break;
          case "TEXT_MESSAGE_CONTENT": patch((m) => ({ ...m, content: m.content + e.delta })); break;
          case "CUSTOM":
            if (e.name === "ui_card") patch((m) => ({ ...m, cards: [...(m.cards || []), e.value] }));
            if (e.name === "guardrail") patch((m) => ({ ...m, guardrails: [...(m.guardrails || []), e.value] }));
            if (e.name === "citations") patch((m) => ({ ...m, citations: e.value }));
            if (e.name === "proposals") patch((m) => ({ ...m, proposals: e.value.map((p: any) => ({ ...p, status: "pending" })) }));
            break;
          case "RUN_ERROR": patch((m) => ({ ...m, error: e.message })); break;
        }
      });
    } catch (err: any) {
      patch((m) => ({ ...m, error: err.message }));
    } finally {
      patch((m) => ({ ...m, streaming: false }));
      setBusy(false);
      sessions.reload();
    }
  };

  const toggleMic = () => {
    if (listening) { recRef.current?.stop(); return; }
    setListening(true);
    recRef.current = startRecognition(lang === "hi" ? "hi-IN" : "en-IN", (t, final) => { setInput(t); if (final) setListening(false); }, () => setListening(false));
    if (!recRef.current) setListening(false);
  };

  return (
    <div className="mx-auto flex h-[calc(100vh-10rem)] max-w-4xl flex-col lg:h-[calc(100vh-7rem)]">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary text-white"><Sparkles className="h-5 w-5" /></span>
          <div>
            <h1 className="text-xl font-semibold leading-tight">AI Health Assistant</h1>
            <div className="text-[0.8rem] text-muted">Answers from your verified records · {status.data?.mode === "llm" ? `AI model: ${status.data.model}` : "Rule-based demo mode (no AI key configured)"}</div>
          </div>
        </div>
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" onClick={() => setShowHistory((s) => !s)}><History /> <span className="hidden sm:inline">Past chats</span></Button>
          <Button variant="outline" size="sm" onClick={() => { setSessionId(null); setMsgs([]); }}><Plus /> New</Button>
        </div>
      </div>

      {showHistory && (
        <Card className="mb-3 max-h-60 overflow-y-auto p-2">
          {(sessions.data?.items || []).length === 0 && <p className="p-3 text-sm text-muted">No past conversations.</p>}
          {(sessions.data?.items || []).map((s) => (
            <div key={s.id} className="flex items-center gap-2 rounded-xl px-3 py-2 hover:bg-muted-bg">
              <button className="min-w-0 flex-1 truncate text-left text-sm" onClick={() => loadSession(s.id)}>{s.title}</button>
              <span className="text-[0.75rem] text-muted">{new Date(s.last_at).toLocaleDateString("en-IN")}</span>
              <button onClick={async () => { await api(`/assistant/sessions/${s.id}`, { method: "DELETE" }); sessions.reload(); }} aria-label="Delete conversation" className="rounded p-1 text-muted hover:text-danger"><Trash2 className="h-4 w-4" /></button>
            </div>
          ))}
        </Card>
      )}

      <div className="flex-1 space-y-5 overflow-y-auto rounded-3xl border border-line bg-surface p-4 sm:p-6" aria-live="polite">
        {msgs.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-3xl bg-secondary text-primary"><Bot className="h-7 w-7" /></span>
            <h2 className="text-lg font-semibold">Ask about your health records</h2>
            <p className="mt-1 max-w-md text-sm text-muted">In English or Hindi. I explain your verified records in simple words. I never diagnose or change medicines.</p>
            <div className="mt-6 grid w-full max-w-2xl gap-2 sm:grid-cols-2">
              {SUGGESTIONS.map((s) => <button key={s} onClick={() => send(s)} className="rounded-2xl border border-line px-4 py-3 text-left text-sm hover:border-primary-300 hover:bg-primary-50">{s}</button>)}
            </div>
          </div>
        )}
        {msgs.map((m) => m.role === "user" ? (
          <div key={m.id} className="flex justify-end"><div className="max-w-[85%] rounded-3xl rounded-br-lg bg-primary px-4 py-3 text-[0.98rem] text-white">{m.content}</div></div>
        ) : (
          <div key={m.id} className="flex gap-3">
            <span className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-secondary text-primary"><Sparkles className="h-4 w-4" /></span>
            <div className="min-w-0 flex-1 space-y-3">
              {!!m.tools?.length && (
                <div className="flex flex-wrap gap-1.5">
                  {m.tools.map((t) => (
                    <span key={t.id} className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[0.75rem]", t.untrusted ? "border-warning/50 bg-warning-bg/60 text-warning-ink" : "border-line bg-background text-muted")} title={t.args}>
                      {t.done ? (t.ok === false ? <ShieldAlert className="h-3.5 w-3.5 text-danger" /> : <Check className="h-3.5 w-3.5 text-primary" />) : <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                      {TOOL_LABEL[t.name] || t.name}
                    </span>
                  ))}
                </div>
              )}
              {m.guardrails?.filter((g) => g.decision !== "pass").map((g, i) => (
                <div key={i} className="flex items-center gap-1.5 text-[0.75rem] text-muted"><ShieldCheck className="h-3.5 w-3.5 text-primary" />Safety check: {String(g.guardrail).replace(/_/g, " ")} — {g.decision}{g.tool ? ` (${g.tool})` : ""}</div>
              ))}
              {m.cards?.map((c, i) => <UICard key={i} card={c} />)}
              {m.content && <div className="whitespace-pre-wrap text-[0.98rem] leading-relaxed text-ink">{m.content}</div>}
              {m.streaming && !m.content && <div className="flex items-center gap-2 text-sm text-muted"><Loader2 className="h-4 w-4 animate-spin" />Thinking…</div>}
              {m.error && <div className="rounded-xl bg-danger-bg px-3 py-2 text-sm text-danger-ink">{m.error}</div>}
              {m.proposals?.map((p) => <Proposal key={p.id} p={p} onDecide={(id, st) => setMsgs((all) => all.map((x) => (x.id === m.id ? { ...x, proposals: x.proposals?.map((q) => (q.id === id ? { ...q, status: st } : q)) } : x)))} />)}
              {!!m.citations?.length && (
                <details className="text-[0.8rem] text-muted">
                  <summary className="cursor-pointer select-none">Sources ({m.citations.length}) <ChevronDown className="inline h-3 w-3" /></summary>
                  <ul className="mt-1.5 space-y-1">{m.citations.map((c, i) => <li key={i} className="flex items-center gap-1.5">{c.flagged ? <ShieldAlert className="h-3.5 w-3.5 text-danger" /> : <FileText className="h-3.5 w-3.5" />}{c.document_id ? <Link href={`/app/documents/${c.document_id}`} className="hover:underline">{c.source}</Link> : c.source}{c.verified ? " · verified" : " · unverified"}</li>)}</ul>
                </details>
              )}
              {!m.streaming && m.content && (speaking && readingId === m.id
                ? <button onClick={stopSpeaking} className="inline-flex items-center gap-1 text-[0.78rem] font-medium text-ink"><Square className="h-3 w-3 fill-current" /> Stop reading</button>
                : <button onClick={() => { const hi = /[ऀ-ॿ]/.test(m.content); setReadingId(m.id); speak(shortForSpeech(m.content, 3, hi), { voice_language: hi ? "hi-IN" : "en-IN" }); }} className="inline-flex items-center gap-1 text-[0.78rem] text-muted hover:text-ink"><Volume2 className="h-3.5 w-3.5" /> Read aloud</button>
              )}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <form onSubmit={(e) => { e.preventDefault(); send(); }} className="mt-3 flex items-end gap-2">
        <div className="relative flex-1">
          <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} rows={1}
            placeholder={lang === "hi" ? "अपना प्रश्न लिखें…" : "Ask about your medicines, reports, diet…"} aria-label="Message"
            className="max-h-36 min-h-[52px] w-full resize-none rounded-2xl border border-input bg-surface px-4 py-3.5 pr-12 text-[0.98rem] focus:border-primary focus:outline-none focus:ring-4 focus:ring-primary/10" />
          {recognitionSupported() && (
            <button type="button" onClick={toggleMic} className={cn("absolute bottom-2.5 right-2.5 rounded-xl p-2", listening ? "bg-danger text-white" : "text-muted hover:bg-muted-bg")} aria-label={listening ? "Stop listening" : "Speak your question"}>
              {listening ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
            </button>
          )}
        </div>
        <Button type="submit" size="icon" className="h-[52px] w-[52px] rounded-2xl" disabled={!input.trim() || busy} aria-label="Send">{busy ? <Loader2 className="animate-spin" /> : <Send />}</Button>
      </form>
      <p className="mt-2 text-center text-[0.75rem] text-muted"><Wrench className="mr-1 inline h-3 w-3" />Educational information from your records — not medical advice. In an emergency call 112.</p>
    </div>
  );
}

export default function AssistantPage() {
  return <Suspense><AssistantInner /></Suspense>;
}
