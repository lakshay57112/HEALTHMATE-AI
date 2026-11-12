"use client";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Check, Coffee, Moon, ShieldCheck, Soup, Sun } from "lucide-react";
import { toast } from "sonner";
import { Logo } from "@/components/common";
import { TagInput } from "@/components/tag-input";
import { Button } from "@/components/ui/button";
import { Card, Checkbox, Field, Input, NativeSelect, Progress, Segmented } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const STEPS = ["About you", "Health", "Food", "Meal times", "Privacy"];

export default function Onboarding() {
  const router = useRouter();
  const { user, loading, setUser } = useAuth();
  const { lang, setLang } = useI18n();
  const [step, setStep] = useState(0);
  const finishing = useRef(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [f, setF] = useState<any>({ date_of_birth: "", gender: "", phone: "", height_cm: "", weight_kg: "", conditions: [], allergies: [], food_preference: "vegetarian", activity_level: "light", budget_preference: "moderate",
    emergency_contact_name: "", emergency_contact_phone: "", meals: { breakfast: "08:30", lunch: "13:00", snack: "17:00", dinner: "20:30" }, ai: false, large_text: false });
  useEffect(() => {
    if (!loading && !user) router.replace("/login");
    if (user?.role === "caregiver") router.replace("/caregiver");
    if (user?.profile?.onboarding_complete && !finishing.current) router.replace("/app");
  }, [user, loading, router]);
  useEffect(() => {
    document.documentElement.classList.toggle("large-text", f.large_text);
  }, [f.large_text]);
  const set = (k: string, v: any) => setF((p: any) => ({ ...p, [k]: v }));

  const next = () => {
    setErr(null);
    if (step === 0 && f.date_of_birth && new Date(f.date_of_birth) > new Date()) return setErr("Date of birth can't be in the future");
    if (step === 3) {
      const t = [f.meals.breakfast, f.meals.lunch, f.meals.snack, f.meals.dinner];
      if (t.some((x) => !x) || [...t].sort().join() !== t.join()) return setErr("Please enter meal times in order: breakfast, lunch, snack, dinner");
    }
    setStep((s) => s + 1);
  };
  const finish = async () => {
    if (!f.ai) return setErr("Please allow AI document processing to continue. You can turn it off later in Settings.");
    setBusy(true);
    try {
      const d = await api("/profile/onboarding", { method: "POST", json: {
        date_of_birth: f.date_of_birth || null, gender: f.gender || null, phone: f.phone || null, height_cm: f.height_cm ? +f.height_cm : null, weight_kg: f.weight_kg ? +f.weight_kg : null,
        conditions: f.conditions, allergies: f.allergies, food_preference: f.food_preference, activity_level: f.activity_level, budget_preference: f.budget_preference,
        emergency_contact_name: f.emergency_contact_name || null, emergency_contact_phone: f.emergency_contact_phone || null, language: lang, large_text: f.large_text,
        meals: Object.entries(f.meals).map(([meal, time]) => ({ meal, time })), ai_processing_consent: true } });
      finishing.current = true;
      setUser(d.user);
      toast.success("You're all set!");
      router.push("/app/documents/new");
    } catch (e: any) {
      setErr(e.message);
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="container max-w-2xl py-8">
        <div className="flex items-center justify-between"><Logo /><Segmented value={lang} onChange={setLang} options={[{ value: "en", label: "EN" }, { value: "hi", label: "हिं" }]} /></div>
        <div className="mt-10">
          <div className="mb-2 flex justify-between text-sm text-muted"><span>Step {step + 1} of {STEPS.length}</span><span>{STEPS[step]}</span></div>
          <Progress value={((step + 1) / STEPS.length) * 100} />
        </div>
        <Card className="mt-6 p-6 sm:p-8 animate-fade-up" key={step}>
          {step === 0 && (
            <div className="space-y-5">
              <div><h1 className="text-2xl font-semibold">Hello{user ? `, ${user.full_name.split(" ")[0]}` : ""} 👋</h1><p className="mt-1 text-muted">A few details help us explain things that fit you. Skip anything you don&apos;t know.</p></div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Date of birth"><Input type="date" value={f.date_of_birth} onChange={(e) => set("date_of_birth", e.target.value)} /></Field>
                <Field label="Gender"><NativeSelect value={f.gender} onChange={(e) => set("gender", e.target.value)}><option value="">Prefer not to say</option><option value="female">Female</option><option value="male">Male</option><option value="other">Other</option></NativeSelect></Field>
                <Field label="Height (cm)"><Input type="number" value={f.height_cm} onChange={(e) => set("height_cm", e.target.value)} /></Field>
                <Field label="Weight (kg)"><Input type="number" value={f.weight_kg} onChange={(e) => set("weight_kg", e.target.value)} /></Field>
                <Field label="Phone"><Input value={f.phone} onChange={(e) => set("phone", e.target.value)} /></Field>
              </div>
              <label className="flex items-center gap-3 rounded-xl bg-background p-4"><Checkbox checked={f.large_text} onCheckedChange={(v) => set("large_text", !!v)} /><span className="font-medium">Use larger text</span></label>
            </div>
          )}
          {step === 1 && (
            <div className="space-y-5">
              <div><h1 className="text-2xl font-semibold">Your health</h1><p className="mt-1 text-muted">Only add conditions your doctor has told you about. We never guess them.</p></div>
              <Field label="Conditions"><TagInput value={f.conditions} onChange={(v) => set("conditions", v)} placeholder="Type and press Enter" suggestions={["Type 2 diabetes", "Hypertension", "High cholesterol", "Hypothyroidism", "Kidney disease", "Heart disease", "Arthritis"]} /></Field>
              <Field label="Food allergies"><TagInput value={f.allergies} onChange={(v) => set("allergies", v)} placeholder="e.g. Peanuts" suggestions={["Peanuts", "Milk", "Gluten", "Egg", "Soy", "Fish"]} /></Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Emergency contact name"><Input value={f.emergency_contact_name} onChange={(e) => set("emergency_contact_name", e.target.value)} /></Field>
                <Field label="Emergency contact phone"><Input value={f.emergency_contact_phone} onChange={(e) => set("emergency_contact_phone", e.target.value)} /></Field>
              </div>
            </div>
          )}
          {step === 2 && (
            <div className="space-y-5">
              <div><h1 className="text-2xl font-semibold">What you like to eat</h1><p className="mt-1 text-muted">Your meal ideas will always follow your doctor&apos;s advice first.</p></div>
              <div className="grid gap-2 sm:grid-cols-2">
                {[["vegetarian", "Vegetarian"], ["eggetarian", "Vegetarian + eggs"], ["non_vegetarian", "Non-vegetarian"], ["vegan", "Vegan"]].map(([v, l]) => (
                  <button key={v} type="button" onClick={() => set("food_preference", v)} className={cn("flex h-14 items-center justify-between rounded-2xl border px-4 font-medium", f.food_preference === v ? "border-primary bg-primary-50 ring-4 ring-primary/10" : "border-line")}>{l}{f.food_preference === v && <Check className="h-5 w-5 text-primary" />}</button>
                ))}
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="How active are you?"><NativeSelect value={f.activity_level} onChange={(e) => set("activity_level", e.target.value)}><option value="sedentary">Mostly sitting</option><option value="light">Light — short walks</option><option value="moderate">Moderate</option><option value="active">Very active</option></NativeSelect></Field>
                <Field label="Food budget"><NativeSelect value={f.budget_preference} onChange={(e) => set("budget_preference", e.target.value)}><option value="low">Budget-friendly</option><option value="moderate">Moderate</option><option value="high">Flexible</option></NativeSelect></Field>
              </div>
            </div>
          )}
          {step === 3 && (
            <div className="space-y-5">
              <div><h1 className="text-2xl font-semibold">When do you usually eat?</h1><p className="mt-1 text-muted">Before-food and after-food medicine reminders are timed from these.</p></div>
              {([["breakfast", Coffee], ["lunch", Sun], ["snack", Soup], ["dinner", Moon]] as const).map(([m, Icon]) => (
                <div key={m} className="flex items-center gap-4">
                  <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-secondary text-primary"><Icon className="h-5 w-5" /></span>
                  <span className="w-28 font-medium capitalize">{m}</span>
                  <Input type="time" className="max-w-[180px]" value={f.meals[m]} onChange={(e) => set("meals", { ...f.meals, [m]: e.target.value })} />
                </div>
              ))}
            </div>
          )}
          {step === 4 && (
            <div className="space-y-5">
              <div><h1 className="text-2xl font-semibold">Your privacy</h1><p className="mt-1 text-muted">Here&apos;s exactly what happens with your information.</p></div>
              <ul className="space-y-3 text-[0.95rem] text-ink-soft">
                {["Documents you upload are encrypted and read by our AI to extract medicines, test values and appointments.", "Nothing is added to your records until you check and confirm it.", "The AI never diagnoses, prescribes or changes a dose.",
                  "Family members only see what you allow, and you can remove them any time.", "You can download or delete all your data from Settings."].map((x) => <li key={x} className="flex gap-2.5"><ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" />{x}</li>)}
              </ul>
              <label className="flex items-start gap-3 rounded-2xl border border-line p-4"><Checkbox checked={f.ai} onCheckedChange={(v) => set("ai", !!v)} className="mt-0.5" /><span className="font-medium">I allow HealthMate to process my documents and questions with AI as described above.</span></label>
            </div>
          )}
          {err && <p className="mt-5 rounded-xl bg-danger-bg px-4 py-3 text-sm text-danger-ink" role="alert">{err}</p>}
          <div className="mt-8 flex justify-between gap-3">
            <Button variant="ghost" size="lg" disabled={step === 0} onClick={() => setStep((s) => s - 1)}><ArrowLeft /> Back</Button>
            {step < STEPS.length - 1 ? <Button size="lg" onClick={next}>Continue <ArrowRight /></Button> : <Button size="lg" onClick={finish} loading={busy}>Finish <Check /></Button>}
          </div>
        </Card>
      </div>
    </div>
  );
}
