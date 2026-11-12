"use client";
/** Device text-to-speech (Web Speech API) + optional speech recognition for the assistant. */

export type VoicePrefs = { voice_language: string; voice_name?: string | null; volume: number; rate: number };

export function ttsSupported() {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function listVoices(): SpeechSynthesisVoice[] {
  if (!ttsSupported()) return [];
  return window.speechSynthesis.getVoices();
}

export function speak(text: string, prefs: Partial<VoicePrefs> = {}) {
  if (!ttsSupported()) return false;
  const u = new SpeechSynthesisUtterance(text);
  const lang = prefs.voice_language || "en-IN";
  u.lang = lang;
  u.rate = prefs.rate ?? 0.9;
  u.volume = prefs.volume ?? 1;
  const voices = listVoices();
  const chosen = voices.find((v) => v.name === prefs.voice_name) || voices.find((v) => v.lang === lang) || voices.find((v) => v.lang.startsWith(lang.slice(0, 2)));
  if (chosen) u.voice = chosen;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
  return true;
}

const SLOT_HI: Record<string, string> = { morning: "सुबह", afternoon: "दोपहर", evening: "शाम", night: "रात" };
const SLOT_HINGLISH: Record<string, string> = { morning: "subah", afternoon: "dopahar", evening: "shaam", night: "raat" };

export function reminderText(dose: { name: string; dosage?: string | null; slot: string; meal_relation?: string }, lang: string, firstName?: string) {
  if (lang.startsWith("hi")) {
    const meal = dose.meal_relation === "after_meal" ? " खाने के बाद" : dose.meal_relation === "before_meal" ? " खाने से पहले" : "";
    return `${firstName ? firstName + " जी, " : ""}आपकी ${SLOT_HI[dose.slot] || ""} की दवा खाने का समय हो गया है। कृपया ${dose.name}${dose.dosage ? ", " + dose.dosage : ""}${meal} लें।`;
  }
  const meal = dose.meal_relation === "after_meal" ? " after your meal" : dose.meal_relation === "before_meal" ? " before your meal" : "";
  return `${firstName ? firstName + ", " : ""}it's time for your ${dose.slot} medicine. Please take ${dose.name}${dose.dosage ? ", " + dose.dosage : ""}${meal}.`;
}

export const SAMPLE_HINGLISH = (slot: string) => `Aapki ${SLOT_HINGLISH[slot] || ""} ki dawai khane ka samay ho gaya hai. Kripya apni prescribed medicine lein.`;

export function recognitionSupported() {
  return typeof window !== "undefined" && ("webkitSpeechRecognition" in window || "SpeechRecognition" in window);
}

export function startRecognition(lang: string, onText: (t: string, final: boolean) => void, onEnd: () => void) {
  const W = window as any;
  const Rec = W.SpeechRecognition || W.webkitSpeechRecognition;
  if (!Rec) return null;
  const r = new Rec();
  r.lang = lang;
  r.interimResults = true;
  r.continuous = false;
  r.onresult = (e: any) => {
    const res = e.results[e.results.length - 1];
    onText(res[0].transcript, res.isFinal);
  };
  r.onend = onEnd;
  r.onerror = onEnd;
  r.start();
  return r;
}
