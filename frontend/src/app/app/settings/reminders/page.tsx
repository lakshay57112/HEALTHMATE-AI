"use client";
import { useEffect, useState } from "react";
import { BellRing, CheckCircle2, Info, Play, Save, XCircle } from "lucide-react";
import { toast } from "sonner";
import { ErrorState, PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, Field, Input, NativeSelect, Segmented, Skeleton, Switch } from "@/components/ui/primitives";
import { api, useApi } from "@/lib/api";
import { enablePush, notificationsSupported } from "@/lib/push";
import { SAMPLE_HINGLISH, listVoices, speak, ttsSupported } from "@/lib/voice";

export default function ReminderSettingsPage() {
  const { data, error, reload } = useApi<any>("/notifications/reminder-settings");
  const [s, setS] = useState<any>(null);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [busy, setBusy] = useState(false);
  const [perm, setPerm] = useState<string>("default");
  useEffect(() => { if (data) setS(data.settings); }, [data]);
  useEffect(() => {
    const load = () => setVoices(listVoices());
    load();
    if (ttsSupported()) window.speechSynthesis.onvoiceschanged = load;
    if (notificationsSupported()) setPerm(Notification.permission);
  }, []);
  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (!s) return <Skeleton className="h-96" />;
  const set = (k: string, v: any) => setS((p: any) => ({ ...p, [k]: v }));
  const langVoices = voices.filter((v) => v.lang.startsWith(s.voice_language.slice(0, 2)));
  const save = async () => {
    setBusy(true);
    try {
      const d = await api("/notifications/reminder-settings", { method: "PUT", json: s });
      setS(d.settings);
      toast.success("Reminder settings saved");
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  };
  const test = () => {
    const text = s.voice_language === "hi-IN" ? "आपकी दोपहर की दवा खाने का समय हो गया है। कृपया अपनी प्रिस्क्राइब की गई दवा लें।" : "It's time for your afternoon medicine. Please take your prescribed medicine.";
    if (!speak(text, s)) toast.error("This browser can't speak aloud.");
  };
  const caps = [
    ["Spoken reminders (text-to-speech)", ttsSupported(), "Plays while HealthMate is open in this browser."],
    ["Device notifications", notificationsSupported() && perm === "granted", perm === "denied" ? "Blocked in browser settings." : "Shown while the app or browser is running."],
    ["Background push (app closed)", !!data?.push?.enabled, data?.push?.enabled ? "Server push is configured." : "Not configured on this server (needs VAPID keys). Reminders still appear in the app."],
  ] as const;
  return (
    <>
      <PageHeader back="/app/settings" title="Voice reminders" description="How HealthMate reminds you to take medicines." actions={<Button onClick={save} loading={busy}><Save /> Save</Button>} />
      <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle>Voice</CardTitle></CardHeader>
            <CardContent className="space-y-5">
              <label className="flex items-center justify-between gap-4"><span className="font-medium">Speak reminders aloud</span><Switch checked={s.voice_enabled} onCheckedChange={(v) => set("voice_enabled", v)} /></label>
              <Field label="Language"><Segmented value={s.voice_language} onChange={(v) => set("voice_language", v)} options={[{ value: "hi-IN", label: "हिंदी" }, { value: "en-IN", label: "English (India)" }]} /></Field>
              <Field label="Voice" hint={langVoices.length ? undefined : "No voice for this language on this device — the default voice will be used."}>
                <NativeSelect value={s.voice_name || ""} onChange={(e) => set("voice_name", e.target.value || null)}><option value="">Device default</option>{langVoices.map((v) => <option key={v.name} value={v.name}>{v.name}</option>)}</NativeSelect>
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={`Volume · ${Math.round(s.volume * 100)}%`}><input type="range" min={0} max={1} step={0.05} value={s.volume} onChange={(e) => set("volume", +e.target.value)} className="w-full accent-primary" /></Field>
                <Field label={`Speed · ${s.rate.toFixed(2)}×`}><input type="range" min={0.5} max={1.5} step={0.05} value={s.rate} onChange={(e) => set("rate", +e.target.value)} className="w-full accent-primary" /></Field>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" onClick={test}><Play /> Play a test reminder</Button>
                <Button variant="ghost" onClick={() => speak(SAMPLE_HINGLISH("afternoon"), { ...s, voice_language: "hi-IN" })}>Hinglish sample</Button>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Timing</CardTitle></CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-3">
              <Field label="Remind me"><NativeSelect value={s.repeat_count} onChange={(e) => set("repeat_count", +e.target.value)}>{[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n === 1 ? "Once" : `${n} times`}</option>)}</NativeSelect></Field>
              <Field label="Every"><NativeSelect value={s.repeat_interval_minutes} onChange={(e) => set("repeat_interval_minutes", +e.target.value)}>{[5, 10, 15, 20, 30].map((n) => <option key={n} value={n}>{n} minutes</option>)}</NativeSelect></Field>
              <Field label="'Remind later' waits"><NativeSelect value={s.snooze_minutes} onChange={(e) => set("snooze_minutes", +e.target.value)}>{[5, 10, 15, 30, 45].map((n) => <option key={n} value={n}>{n} minutes</option>)}</NativeSelect></Field>
              <Field label="Quiet hours from"><Input type="time" value={s.quiet_hours_start || ""} onChange={(e) => set("quiet_hours_start", e.target.value || null)} /></Field>
              <Field label="to"><Input type="time" value={s.quiet_hours_end || ""} onChange={(e) => set("quiet_hours_end", e.target.value || null)} /></Field>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Notifications</CardTitle></CardHeader>
            <CardContent className="divide-y divide-line">
              {[["in_app_enabled", "In-app reminders"], ["push_enabled", "Push notifications"], ["refill_alerts", "Refill reminders"], ["appointment_alerts", "Appointment reminders"]].map(([k, l]) => (
                <label key={k} className="flex items-center justify-between py-3"><span>{l}</span><Switch checked={!!s[k]} onCheckedChange={(v) => set(k, v)} /></label>
              ))}
            </CardContent>
          </Card>
        </div>
        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle>On this device</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {caps.map(([label, ok, note]) => (
                <div key={label} className="flex items-start gap-2.5 text-sm">{ok ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" /> : <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-muted" />}<div><div className="font-medium">{label}</div><div className="text-muted">{note}</div></div></div>
              ))}
              <Button className="w-full" variant="outline" onClick={async () => { const r = await enablePush(); toast[r.ok ? "success" : "error"](r.message); if (notificationsSupported()) setPerm(Notification.permission); }}><BellRing /> Allow notifications</Button>
            </CardContent>
          </Card>
          <Card className="p-5 text-sm text-ink-soft">
            <div className="mb-2 flex items-center gap-2 font-medium text-ink"><Info className="h-4 w-4 text-primary" /> Good to know</div>
            Browsers can&apos;t speak or run reminders reliably when HealthMate is fully closed. With push configured, you&apos;ll still get a silent notification; tap it to hear the reminder. Missed-dose alerts to your family are sent by the server either way.
          </Card>
        </div>
      </div>
    </>
  );
}
