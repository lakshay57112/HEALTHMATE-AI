"use client";
import Link from "next/link";
import { useState } from "react";
import { Activity, BellRing, Bot, Brain, ChevronRight, Copy, Cpu, Database, Download, KeyRound, Languages, Lock, ScrollText, ShieldCheck, Terminal, Trash2, Type, Volume2 } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Badge, Card, CardContent, CardHeader, CardTitle, Field, Input, Segmented, Switch, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/primitives";
import { api, useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { enablePush } from "@/lib/push";
import { cn, fmtDateTime } from "@/lib/utils";

function Row({ icon: Icon, title, desc, children }: { icon: any; title: string; desc?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3"><Icon className="mt-0.5 h-5 w-5 shrink-0 text-muted" /><div><div className="font-medium">{title}</div>{desc && <div className="text-sm text-muted">{desc}</div>}</div></div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function General() {
  const { lang, setLang } = useI18n();
  const { user, setUser } = useAuth();
  const [pushMsg, setPushMsg] = useState<string | null>(null);
  const update = async (body: any) => {
    const d = await api("/profile", { method: "PUT", json: body });
    setUser(d.user);
  };
  return (
    <Card><CardContent className="divide-y divide-line py-1">
      <Row icon={Languages} title="Language" desc="Menus, explanations and voice reminders"><Segmented value={lang} onChange={(v) => { setLang(v); update({ language: v }); }} options={[{ value: "en", label: "English" }, { value: "hi", label: "हिंदी" }]} /></Row>
      <Row icon={Type} title="Large text" desc="Bigger letters across the app"><Switch checked={!!user?.profile?.large_text} onCheckedChange={(v) => update({ large_text: v })} aria-label="Large text" /></Row>
      <Row icon={Volume2} title="Voice reminders" desc="Language, voice, volume, repeats"><Button asChild variant="outline" size="sm"><Link href="/app/settings/reminders">Open <ChevronRight /></Link></Button></Row>
      <Row icon={BellRing} title="Notifications on this device" desc={pushMsg || "Allow reminders to appear as notifications"}>
        <Button size="sm" onClick={async () => { const r = await enablePush(); setPushMsg(r.message); r.ok ? toast.success(r.message) : toast.error(r.message); }}>Enable</Button>
      </Row>
    </CardContent></Card>
  );
}

function Privacy() {
  const consents = useApi<{ items: any[] }>("/consents");
  const audit = useApi<{ items: any[] }>("/account/audit?limit=60");
  const { user } = useAuth();
  const [del, setDel] = useState(false);
  const [pw, setPw] = useState("");
  const [confirmText, setConfirmText] = useState("");
  const ai = consents.data?.items.find((c) => c.type === "ai_processing");
  return (
    <div className="space-y-6">
      <Card><CardContent className="divide-y divide-line py-1">
        <Row icon={Bot} title="AI document processing & assistant" desc="Needed to read uploads and answer questions. Turning off stops new processing.">
          <Switch checked={!!ai?.granted} onCheckedChange={async (v) => { await api("/consents", { method: "POST", json: { consent_type: "ai_processing", granted: v } }); consents.reload(); }} aria-label="AI processing consent" />
        </Row>
        <Row icon={Download} title="Download my data" desc="Everything we store, as a JSON file"><Button asChild variant="outline" size="sm"><a href="/api/account/export">Download</a></Button></Row>
        <Row icon={Trash2} title="Delete my account" desc="Permanently deletes your account, documents and history"><Button variant="danger-outline" size="sm" onClick={() => setDel(true)}>Delete…</Button></Row>
      </CardContent></Card>
      <Card>
        <CardHeader><div><CardTitle className="flex items-center gap-2"><ScrollText className="h-4 w-4" /> Activity log</CardTitle><p className="text-sm text-muted">Who accessed or changed your information. No medical content is stored here.</p></div></CardHeader>
        <CardContent className="max-h-96 space-y-1 overflow-y-auto">
          {(audit.data?.items || []).map((a) => (
            <div key={a.id} className="flex items-center justify-between gap-3 rounded-lg px-2 py-1.5 text-sm hover:bg-muted-bg">
              <span><b className="font-medium">{a.actor}</b> <span className="text-muted">{a.action.replace(/[._]/g, " ")}</span></span>
              <span className="shrink-0 text-[0.78rem] text-muted">{fmtDateTime(a.at)}</span>
            </div>
          ))}
        </CardContent>
      </Card>
      <Card><CardContent className="space-y-1 py-4 text-sm text-ink-soft">
        <div className="flex items-center gap-2 font-medium text-ink"><Lock className="h-4 w-4 text-primary" /> How your data is protected</div>
        <p>• Documents and sensitive text are encrypted at rest. • Sessions use secure, HTTP-only cookies. • Caregivers only see what you allow. • The AI cannot send your data anywhere.</p>
      </CardContent></Card>
      <Dialog open={del} onOpenChange={setDel}>
        <DialogContent title="Delete account permanently?" description="This removes all your documents, medicines, reports, caregivers and history. It cannot be undone.">
          <div className="space-y-4">
            {!user?.is_demo && <Field label="Password"><Input type="password" value={pw} onChange={(e) => setPw(e.target.value)} /></Field>}
            <Field label='Type "DELETE" to confirm'><Input value={confirmText} onChange={(e) => setConfirmText(e.target.value)} /></Field>
            <div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setDel(false)}>Cancel</Button>
              <Button variant="danger" disabled={confirmText !== "DELETE"} onClick={async () => { try { await api("/account/delete", { method: "POST", json: { password: pw || "demo", confirm: confirmText } }); window.location.href = "/"; } catch (e: any) { toast.error(e.message); } }}>Delete everything</Button></div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function AIActivity() {
  const traces = useApi<{ items: any[] }>("/assistant/traces?limit=40");
  const memory = useApi<{ items: any[] }>("/assistant/memory");
  const status = useApi<any>("/assistant/status");
  const [open, setOpen] = useState<string | null>(null);
  const detail = useApi<any>(open ? `/assistant/traces/${open}` : null, [open]);
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="p-5"><div className="eyebrow">Mode</div><div className="mt-1 text-lg font-semibold">{status.data?.mode === "llm" ? "AI model" : "Rule-based demo"}</div><div className="text-sm text-muted">{status.data?.model}</div></Card>
        <Card className="p-5"><div className="eyebrow">Runs logged</div><div className="mt-1 text-lg font-semibold tnum">{traces.data?.items.length ?? "—"}</div><div className="text-sm text-muted">assistant + document pipeline</div></Card>
        <Card className="p-5"><div className="eyebrow">Guardrail events</div><div className="mt-1 text-lg font-semibold tnum">{(traces.data?.items || []).reduce((n, t) => n + t.guardrail_events.filter((g: any) => g.decision !== "pass").length, 0)}</div><div className="text-sm text-muted">blocked, flagged or softened</div></Card>
      </div>
      <Card>
        <CardHeader><div><CardTitle className="flex items-center gap-2"><Activity className="h-4 w-4" /> Recent AI runs</CardTitle><p className="text-sm text-muted">Each run is traced step by step. Traces store timings and decisions — not your medical text.</p></div></CardHeader>
        <CardContent className="space-y-1.5">
          {(traces.data?.items || []).map((t) => (
            <div key={t.id}>
              <button onClick={() => setOpen(open === t.id ? null : t.id)} className="flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left text-sm hover:bg-muted-bg">
                <span className="flex items-center gap-2"><Badge variant={t.kind === "assistant" ? "primary" : "info"}>{t.kind}</Badge><span className="text-muted">{t.model}</span></span>
                <span className="flex items-center gap-3 text-[0.8rem] text-muted tnum">{t.span_count} steps · {t.total_ms} ms{t.tokens_in ? ` · ${t.tokens_in}+${t.tokens_out} tok${t.cached_tokens ? ` (${t.cached_tokens} cached)` : ""}` : ""}<span>{fmtDateTime(t.created_at)}</span></span>
              </button>
              {open === t.id && detail.data && (
                <div className="mb-2 ml-3 space-y-1 border-l-2 border-line pl-4">
                  {detail.data.trace.spans.map((s: any, i: number) => (
                    <div key={i} className="flex items-center justify-between gap-3 text-[0.82rem]">
                      <span className={cn("font-mono", s.status !== "ok" && "text-danger-ink")}>{s.kind === "tool" ? "🔧 " : s.kind === "guardrail" ? "🛡 " : s.kind === "llm" ? "🧠 " : "• "}{s.name}{s.attrs?.detail ? <span className="font-sans text-muted"> — {s.attrs.detail}</span> : null}</span>
                      <span className="shrink-0 text-muted tnum">{s.duration_ms} ms</span>
                    </div>
                  ))}
                  {detail.data.trace.guardrail_events.map((g: any, i: number) => <div key={"g" + i} className="text-[0.8rem] text-warning-ink">🛡 {g.guardrail}: {g.decision} {g.detail && `— ${g.detail}`}</div>)}
                </div>
              )}
            </div>
          ))}
          {!traces.data?.items.length && <p className="text-sm text-muted">No AI runs yet.</p>}
        </CardContent>
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><div><CardTitle className="flex items-center gap-2"><Brain className="h-4 w-4" /> What the assistant remembers</CardTitle><p className="text-sm text-muted">Only things you explicitly asked it to remember.</p></div></CardHeader>
          <CardContent className="space-y-2">
            {(memory.data?.items || []).map((m) => (
              <div key={m.id} className="flex items-center justify-between gap-2 rounded-xl bg-background px-3 py-2 text-sm"><span>{m.content}</span>
                <Button variant="ghost" size="icon-sm" aria-label="Forget" onClick={async () => { await api(`/assistant/memory/${m.id}`, { method: "DELETE" }); memory.reload(); }}><Trash2 /></Button></div>
            ))}
            {!memory.data?.items.length && <p className="text-sm text-muted">Nothing saved. Say &quot;remember that…&quot; in a chat to add something.</p>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><ShieldCheck className="h-4 w-4" /> Tools the assistant can use</CardTitle></CardHeader>
          <CardContent className="space-y-1.5">
            {(status.data?.tools || []).map((t: any) => (
              <div key={t.name} className="flex items-center justify-between gap-2 text-[0.82rem]"><span className="font-mono">{t.name}</span>
                <span className="flex gap-1">{t.writes ? <Badge variant="warning">needs approval</Badge> : <Badge>read-only</Badge>}{t.reads_untrusted && <Badge variant="info">untrusted text</Badge>}</span></div>
            ))}
            <p className="pt-2 text-[0.78rem] text-muted">No tool can send data outside the app. After reading uploaded text, write tools are switched off for that answer (prompt-injection protection).</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Developer() {
  const [token, setToken] = useState<string | null>(null);
  const sys = useApi<any>("/system/status");
  const cfg = token ? JSON.stringify({ mcpServers: { healthmate: { command: "python", args: ["/path/to/healthmate-ai/backend/mcp_server.py"], env: { HEALTHMATE_API_URL: `${window.location.origin}/api`, HEALTHMATE_TOKEN: token } } } }, null, 2) : "";
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader><div><CardTitle className="flex items-center gap-2"><Terminal className="h-4 w-4" /> Connect via MCP</CardTitle><p className="text-sm text-muted">Use your HealthMate data (read-only) from MCP clients such as Claude Desktop.</p></div></CardHeader>
        <CardContent className="space-y-3">
          <Button variant="outline" onClick={async () => { const d = await api("/auth/token", { method: "POST" }); setToken(d.access_token); }}><KeyRound /> Create a personal API token</Button>
          {token && (
            <>
              <p className="text-sm text-warning-ink">Keep this token private — it gives read access to your health data until it expires.</p>
              <pre className="max-h-64 overflow-auto rounded-xl bg-ink p-4 font-mono text-[0.75rem] text-white">{cfg}</pre>
              <Button size="sm" variant="outline" onClick={() => { navigator.clipboard.writeText(cfg); toast.success("Copied"); }}><Copy /> Copy config</Button>
            </>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Cpu className="h-4 w-4" /> System status</CardTitle></CardHeader>
        <CardContent className="grid gap-2 text-sm sm:grid-cols-2">
          {sys.data && [
            ["AI model", sys.data.llm.mode === "live" ? `${sys.data.llm.provider} · ${sys.data.llm.model}` : "Demo mode (no API key) — rule-based extraction & assistant"],
            ["OCR", sys.data.ocr.available ? `Tesseract (${sys.data.ocr.languages})` : "Not installed"],
            ["Background push", sys.data.push.enabled ? "Configured (VAPID)" : "Not configured — in-app + voice while open"],
            ["Reminder engine", sys.data.reminder_engine.enabled ? `Running every ${sys.data.reminder_engine.tick_seconds}s` : "Off"],
            ["Email", sys.data.email.note], ["API docs", "/api/docs"],
          ].map(([k, v]) => <div key={k} className="rounded-xl bg-background px-3.5 py-2.5"><div className="text-[0.75rem] text-muted">{k}</div><div className="font-medium">{k === "API docs" ? <a className="text-primary" href="/api/docs" target="_blank">{v}</a> : v}</div></div>)}
        </CardContent>
      </Card>
    </div>
  );
}

export default function SettingsPage() {
  const { t } = useI18n();
  return (
    <>
      <PageHeader title={t("Settings")} description="Language, accessibility, privacy and AI transparency." />
      <Tabs defaultValue="general">
        <TabsList className="mb-5">
          <TabsTrigger value="general">General</TabsTrigger><TabsTrigger value="privacy">Privacy & data</TabsTrigger><TabsTrigger value="ai">AI activity</TabsTrigger><TabsTrigger value="dev">Developer</TabsTrigger>
        </TabsList>
        <TabsContent value="general"><General /></TabsContent>
        <TabsContent value="privacy"><Privacy /></TabsContent>
        <TabsContent value="ai"><AIActivity /></TabsContent>
        <TabsContent value="dev"><Developer /></TabsContent>
      </Tabs>
    </>
  );
}

const _u = Database;
