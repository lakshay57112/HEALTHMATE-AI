import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmtTime(hhmm?: string | null) {
  if (!hhmm) return "";
  const [h, m] = hhmm.split(":").map(Number);
  return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;
}

export function fmtDate(iso?: string | null, opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric" }) {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? iso + "T00:00:00" : iso);
  return isNaN(d.getTime()) ? "—" : d.toLocaleDateString("en-IN", opts);
}

export function fmtDateTime(iso?: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

export function relDays(iso?: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  const today = new Date();
  const diff = Math.round((new Date(d.toDateString()).getTime() - new Date(today.toDateString()).getTime()) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Tomorrow";
  if (diff === -1) return "Yesterday";
  if (diff > 1 && diff < 7) return `In ${diff} days`;
  if (diff < 0 && diff > -7) return `${-diff} days ago`;
  return fmtDate(iso);
}

export function initials(name?: string) {
  return (name || "?").split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
}

export const SLOT_META = {
  morning: { en: "Morning", hi: "सुबह", icon: "sunrise" },
  afternoon: { en: "Afternoon", hi: "दोपहर", icon: "sun" },
  evening: { en: "Evening", hi: "शाम", icon: "sunset" },
  night: { en: "Night", hi: "रात", icon: "moon" },
} as const;

export const MEAL_REL: Record<string, { en: string; hi: string }> = {
  before_meal: { en: "Before food", hi: "खाने से पहले" },
  after_meal: { en: "After food", hi: "खाने के बाद" },
  with_meal: { en: "With food", hi: "खाने के साथ" },
  empty_stomach: { en: "Empty stomach", hi: "खाली पेट" },
  bedtime: { en: "At bedtime", hi: "सोने से पहले" },
  any: { en: "Any time", hi: "किसी भी समय" },
};

export const DOC_TYPES: Record<string, { en: string; hi: string }> = {
  auto: { en: "Detect automatically", hi: "अपने आप पहचानें" },
  lab_report: { en: "Lab / blood report", hi: "लैब / ब्लड रिपोर्ट" },
  prescription: { en: "Prescription", hi: "पर्चा" },
  consultation_note: { en: "Doctor's note", hi: "डॉक्टर का नोट" },
  diet_advice: { en: "Diet advice", hi: "आहार सलाह" },
  appointment: { en: "Appointment", hi: "अपॉइंटमेंट" },
  other: { en: "Other document", hi: "अन्य दस्तावेज़" },
};

export const RELATIONSHIPS = ["son", "daughter", "spouse", "family", "housemate", "caretaker"] as const;

export function pct(n?: number | null) {
  return n == null ? "—" : `${n}%`;
}
