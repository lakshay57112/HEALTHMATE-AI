"use client";
/** Device text-to-speech (Web Speech API) + optional speech recognition for the assistant. */
import { useSyncExternalStore } from "react";

export type VoicePrefs = { voice_language: string; voice_name?: string | null; volume: number; rate: number };

export function ttsSupported() {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function listVoices(): SpeechSynthesisVoice[] {
  if (!ttsSupported()) return [];
  return window.speechSynthesis.getVoices();
}

/* One shared "is something being read aloud?" state, so any screen can show a Stop button. */
let speakingNow = false;
let generation = 0; // bumps on every speak/stop, so callbacks from cancelled speech are ignored
const listeners = new Set<() => void>();
function setSpeaking(v: boolean) {
  if (speakingNow === v) return;
  speakingNow = v;
  listeners.forEach((l) => l());
}
function subscribe(l: () => void) {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
}
export function isSpeaking() {
  return speakingNow;
}
export function useSpeaking() {
  return useSyncExternalStore(subscribe, isSpeaking, () => false);
}

export function stopSpeaking() {
  generation++;
  if (ttsSupported()) window.speechSynthesis.cancel();
  setSpeaking(false);
}

/** Split into sentence-sized pieces: long single utterances can't be interrupted cleanly in some browsers. */
function chunks(text: string): string[] {
  const parts = text.replace(/\s+/g, " ").trim().match(/[^.!?।]+[.!?।]*/g) || [];
  const out: string[] = [];
  for (const p of parts.map((x) => x.trim()).filter(Boolean)) {
    if (out.length && (out[out.length - 1] + " " + p).length < 160) out[out.length - 1] += " " + p;
    else out.push(p);
  }
  return out;
}

export function speak(text: string, prefs: Partial<VoicePrefs> = {}) {
  if (!ttsSupported()) return false;
  stopSpeaking();
  const gen = generation;
  const lang = prefs.voice_language || "en-IN";
  const voices = listVoices();
  const chosen = voices.find((v) => v.name === prefs.voice_name) || voices.find((v) => v.lang === lang) || voices.find((v) => v.lang.startsWith(lang.slice(0, 2)));
  const pieces = chunks(text);
  if (!pieces.length) return false;
  pieces.forEach((piece, i) => {
    const u = new SpeechSynthesisUtterance(piece);
    u.lang = lang;
    u.rate = prefs.rate ?? 0.9;
    u.volume = prefs.volume ?? 1;
    if (chosen) u.voice = chosen;
    u.onstart = () => {
      if (gen === generation) setSpeaking(true);
    };
    u.onerror = () => {
      if (gen === generation) setSpeaking(false);
    };
    if (i === pieces.length - 1) {
      u.onend = () => {
        if (gen === generation) setSpeaking(false);
      };
    }
    window.speechSynthesis.speak(u);
  });
  setSpeaking(true);
  return true;
}

/** Spoken version of a long answer: the first few sentences, then a pointer to the screen. */
export function shortForSpeech(text: string, maxSentences = 3, hindi = false) {
  const clean = text.replace(/ℹ️.*/s, "").replace(/[*_#>`]/g, "").replace(/^\s*[-•]\s*/gm, "").replace(/\s+/g, " ").trim();
  const sentences = clean.match(/[^.!?।]+[.!?।]+/g) || [clean];
  if (sentences.length <= maxSentences) return clean;
  return sentences.slice(0, maxSentences).join(" ").trim() + (hindi ? " पूरा जवाब स्क्रीन पर है।" : " The full answer is on your screen.");
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
