"use client";
import { useState } from "react";
import { Loader2, PlayCircle } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export function DemoButton({ role = "patient", className, label }: { role?: "patient" | "caregiver"; className?: string; label?: string }) {
  const [busy, setBusy] = useState(false);
  return (
    <button
      onClick={async () => {
        setBusy(true);
        try {
          await api(`/auth/demo?role=${role}`, { method: "POST" });
          window.location.href = role === "patient" ? "/app" : "/caregiver";
        } catch (e: any) {
          toast.error(e.message);
          setBusy(false);
        }
      }}
      className={cn("inline-flex h-14 items-center justify-center gap-2 rounded-2xl border border-line-strong bg-surface px-7 text-[1.02rem] font-medium hover:bg-muted-bg", className)}
    >
      {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <PlayCircle className="h-5 w-5 text-primary" />} {label || "Try the demo"}
    </button>
  );
}
