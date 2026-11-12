"use client";
import { useState } from "react";
import { AlertTriangle, Check, Clock, Moon, SkipForward, Sun, Sunrise, Sunset } from "lucide-react";
import { toast } from "sonner";
import { StatusPill } from "@/components/common";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { MEAL_REL, cn, fmtTime } from "@/lib/utils";

export const SLOT_ICONS = { morning: Sunrise, afternoon: Sun, evening: Sunset, night: Moon } as const;

export type Dose = {
  schedule_id: string; medicine_id: string; name: string; strength: string | null; dosage: string | null; form: string | null; color: string | null; slot: keyof typeof SLOT_ICONS;
  time: string; effective_time: string; meal_relation: string; rule: string; advisory: string | null; instructions: string | null; scheduled_for: string; status: string; acted_at: string | null;
};

export function PillDot({ color, className }: { color?: string | null; className?: string }) {
  return (
    <span className={cn("relative inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl", className)} style={{ background: `${color || "#4D8B73"}1A` }}>
      <span className="h-4 w-6 rounded-full" style={{ background: `linear-gradient(90deg, ${color || "#4D8B73"} 50%, ${color || "#4D8B73"}66 50%)` }} />
    </span>
  );
}

export function DoseRow({ dose, onChange, compact }: { dose: Dose; onChange?: () => void; compact?: boolean }) {
  const { t, lang } = useI18n();
  const [busy, setBusy] = useState<string | null>(null);
  const act = async (action: "taken" | "skipped" | "snoozed") => {
    setBusy(action);
    try {
      await api("/medicines/doses/action", { method: "POST", json: { schedule_id: dose.schedule_id, scheduled_for: dose.scheduled_for, action } });
      toast.success(action === "taken" ? `${dose.name} marked as taken` : action === "snoozed" ? "We'll remind you again soon" : `${dose.name} skipped`);
      window.dispatchEvent(new CustomEvent("hm:doses-changed"));
      onChange?.();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(null);
    }
  };
  const actionable = ["due", "overdue", "upcoming", "snoozed", "missed"].includes(dose.status);
  return (
    <div className={cn("flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4 sm:flex-row sm:items-center", dose.status === "due" && "border-warning/60 bg-warning-bg/30")}>
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <PillDot color={dose.color} />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="text-[1.02rem] font-semibold">{dose.name}</span>
            {dose.strength && <span className="text-sm text-muted">{dose.strength}</span>}
            <StatusPill status={dose.status} />
          </div>
          <div className="mt-0.5 text-sm text-muted">
            <span className="font-medium text-ink-soft tnum">{fmtTime(dose.effective_time)}</span>
            <span className="divider-dot" />
            {dose.dosage || "As prescribed"}
            {dose.meal_relation !== "any" && (<><span className="divider-dot" />{MEAL_REL[dose.meal_relation]?.[lang] ?? dose.meal_relation}</>)}
          </div>
          {dose.advisory && !compact && (
            <div className="mt-1.5 flex items-start gap-1.5 text-[0.82rem] text-warning-ink"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />{dose.advisory}</div>
          )}
        </div>
      </div>
      {actionable && (
        <div className="flex gap-2 sm:shrink-0">
          <Button size={compact ? "sm" : "default"} className="flex-1 sm:flex-none" loading={busy === "taken"} disabled={!!busy} onClick={() => act("taken")}>
            <Check /> {t("Mark taken")}
          </Button>
          {!compact && (
            <>
              <Button variant="outline" size="icon" disabled={!!busy} onClick={() => act("snoozed")} aria-label={t("Remind later")} title={t("Remind later")}><Clock /></Button>
              <Button variant="ghost" size="icon" disabled={!!busy} onClick={() => act("skipped")} aria-label={t("Skip")} title={t("Skip")}><SkipForward /></Button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
