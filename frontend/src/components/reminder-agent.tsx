"use client";
/**
 * In-app reminder agent: while the app is open, checks today's doses every 30 s. When a dose becomes due it
 * speaks the reminder (device TTS, Hindi or English), shows a browser notification (if allowed) and an in-app
 * prompt with Taken / Remind later. Background reminders when the app is closed rely on Web Push (server VAPID
 * keys) — see Settings → Reminders for the live status on this device.
 */
import { useEffect, useRef, useState } from "react";
import { BellRing, Check, Clock, Volume2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { showLocalNotification } from "@/lib/push";
import { cn, fmtTime } from "@/lib/utils";
import { reminderText, speak } from "@/lib/voice";

type Dose = { schedule_id: string; scheduled_for: string; name: string; strength: string | null; dosage: string | null; slot: string; effective_time: string; status: string; meal_relation: string };

export function ReminderAgent() {
  const { user } = useAuth();
  const [active, setActive] = useState<Dose | null>(null);
  const [busy, setBusy] = useState(false);
  const spoken = useRef<Set<string>>(new Set());
  const prefs = useRef<any>(null);

  useEffect(() => {
    if (!user || user.role !== "patient") return;
    let alive = true;
    api("/notifications/reminder-settings").then((d) => (prefs.current = d.settings)).catch(() => {});
    try {
      spoken.current = new Set(JSON.parse(sessionStorage.getItem("hm_spoken") || "[]"));
    } catch {}
    const check = async () => {
      try {
        const d = await api<{ doses: Dose[] }>("/medicines/today");
        if (!alive) return;
        const due = d.doses.find((x) => x.status === "due" && !spoken.current.has(`${x.schedule_id}|${x.scheduled_for}`));
        if (due) {
          const key = `${due.schedule_id}|${due.scheduled_for}`;
          spoken.current.add(key);
          try {
            sessionStorage.setItem("hm_spoken", JSON.stringify([...spoken.current].slice(-50)));
          } catch {}
          setActive(due);
          const p = prefs.current || { voice_enabled: true, voice_language: user.language === "hi" ? "hi-IN" : "en-IN", rate: 0.9, volume: 1 };
          const text = reminderText(due, p.voice_language, user.full_name.split(" ")[0]);
          if (p.voice_enabled !== false) speak(text, p);
          showLocalNotification("Time for your medicine", `${due.name} ${due.strength || ""} — ${due.dosage || "as prescribed"}`);
        }
      } catch {}
    };
    check();
    const id = setInterval(check, 30000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [user]);

  if (!active) return null;
  const act = async (action: "taken" | "snoozed") => {
    setBusy(true);
    try {
      await api("/medicines/doses/action", { method: "POST", json: { schedule_id: active.schedule_id, scheduled_for: active.scheduled_for, action } });
      window.dispatchEvent(new CustomEvent("hm:doses-changed"));
      setActive(null);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="fixed inset-x-3 bottom-24 z-50 mx-auto max-w-md animate-fade-up lg:bottom-6 lg:right-6 lg:left-auto lg:mx-0" role="alertdialog" aria-live="assertive" aria-label="Medicine reminder">
      <div className="rounded-3xl border border-primary-200 bg-surface p-5 shadow-lift">
        <div className="flex items-start gap-3">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary text-white animate-pulse-ring"><BellRing className="h-6 w-6" /></span>
          <div className="min-w-0 flex-1">
            <div className="eyebrow text-primary">Medicine reminder · {fmtTime(active.effective_time)}</div>
            <div className="mt-1 text-lg font-semibold leading-snug">{active.name} {active.strength}</div>
            <div className="text-sm text-muted">{active.dosage || "As prescribed"}{active.meal_relation === "after_meal" ? " · after food" : active.meal_relation === "before_meal" ? " · before food" : ""}</div>
          </div>
          <button onClick={() => setActive(null)} className="rounded-lg p-1.5 text-muted hover:bg-muted-bg" aria-label="Dismiss"><X className="h-5 w-5" /></button>
        </div>
        <div className="mt-4 grid grid-cols-[1fr_auto_auto] gap-2">
          <Button size="lg" className="h-12" loading={busy} onClick={() => act("taken")}><Check /> Taken</Button>
          <Button size="lg" variant="outline" className="h-12" disabled={busy} onClick={() => act("snoozed")}><Clock /> Later</Button>
          <Button size="icon" variant="ghost" className={cn("h-12 w-12")} aria-label="Repeat reminder aloud"
            onClick={() => speak(reminderText(active, prefs.current?.voice_language || "hi-IN", user?.full_name.split(" ")[0]), prefs.current || {})}>
            <Volume2 />
          </Button>
        </div>
      </div>
    </div>
  );
}
