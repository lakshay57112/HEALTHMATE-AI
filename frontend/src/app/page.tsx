import Link from "next/link";
import { ArrowRight, BellRing, Check, FileScan, HeartHandshake, Languages, Lock, MessageCircleQuestion, Pill, Salad, ShieldCheck, Sparkles, Upload } from "lucide-react";
import { Logo } from "@/components/common";
import { DemoButton } from "./demo-button";

const FEATURES = [
  { icon: FileScan, title: "Understand every report", body: "Upload a blood test and get each value explained in simple English or Hindi — with your lab's own ranges, never guessed ones." },
  { icon: Pill, title: "Prescriptions become reminders", body: "We read each medicine, dose and timing. You check it once, and a meal-aware schedule is ready." },
  { icon: BellRing, title: "Voice reminders that speak your language", body: "“Aapki dopahar ki dawai ka samay ho gaya hai.” Gentle spoken reminders with one-tap Taken or Later." },
  { icon: Salad, title: "Meals that follow your doctor", body: "Food ideas built around your doctor's advice, your reports, allergies and preferences — never contradicting them." },
  { icon: HeartHandshake, title: "Family stays in the loop", body: "Up to three trusted people get an alert if a dose is missed — only with your permission, only what you choose." },
  { icon: MessageCircleQuestion, title: "Ask anything, anytime", body: "“When is my next appointment?” “Explain my cholesterol in Hindi.” Answers come from your verified records." },
];

export default function Landing() {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-30 border-b border-line/70 bg-background/85 backdrop-blur">
        <div className="container flex h-16 items-center justify-between">
          <Logo />
          <nav className="flex items-center gap-2">
            <Link href="/login" className="hidden h-10 items-center rounded-xl px-4 text-sm font-medium text-ink-soft hover:bg-muted-bg sm:inline-flex">Sign in</Link>
            <Link href="/register" className="inline-flex h-10 items-center rounded-xl bg-primary px-4 text-sm font-medium text-white hover:bg-primary-600">Get started</Link>
          </nav>
        </div>
      </header>

      <section className="container grid items-center gap-12 pb-16 pt-14 lg:grid-cols-[1.05fr_1fr] lg:pt-20">
        <div className="animate-fade-up">
          <span className="inline-flex items-center gap-2 rounded-full border border-primary-200 bg-primary-50 px-3 py-1 text-[0.8rem] font-medium text-primary-800"><Sparkles className="h-3.5 w-3.5" /> Upload once. Understand everything.</span>
          <h1 className="mt-5 text-[2.6rem] font-semibold leading-[1.08] tracking-tight sm:text-[3.4rem]">Your health. Your family.<br /><span className="text-primary">One intelligent companion.</span></h1>
          <p className="mt-5 max-w-xl text-lg leading-relaxed text-ink-soft">HealthMate reads your prescriptions and medical reports, explains them in plain language, reminds you to take medicines, and keeps your family informed — all from one calm place.</p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link href="/register" className="inline-flex h-14 items-center justify-center gap-2 rounded-2xl bg-primary px-7 text-[1.02rem] font-medium text-white shadow-sm hover:bg-primary-600">Create free account <ArrowRight className="h-5 w-5" /></Link>
            <DemoButton />
          </div>
          <div className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted">
            <span className="flex items-center gap-1.5"><Languages className="h-4 w-4 text-primary" /> English & हिंदी</span>
            <span className="flex items-center gap-1.5"><Lock className="h-4 w-4 text-primary" /> Encrypted documents</span>
            <span className="flex items-center gap-1.5"><ShieldCheck className="h-4 w-4 text-primary" /> You approve every change</span>
          </div>
        </div>

        <div className="relative">
          <div className="card relative overflow-hidden p-6 shadow-lift">
            <div className="flex items-center justify-between">
              <div><div className="eyebrow">Next medicine</div><div className="mt-1 text-3xl font-semibold tnum">1:15 PM</div><div className="text-ink-soft">Calcium + Vitamin D3 · 1 tablet · after lunch</div></div>
              <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-secondary"><Pill className="h-7 w-7 text-primary" /></span>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-2">
              <span className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-primary font-medium text-white"><Check className="h-5 w-5" /> Taken</span>
              <span className="inline-flex h-12 items-center justify-center rounded-xl border border-line-strong font-medium">Remind later</span>
            </div>
            <div className="mt-6 rounded-2xl bg-background p-4">
              <div className="flex items-center gap-2 text-sm font-semibold"><FileScan className="h-4 w-4 text-primary" /> Diabetes & Lipid Profile</div>
              <p className="mt-1.5 text-sm text-ink-soft">HbA1c is <b>7.4%</b> — above your lab&apos;s range (4.0–5.6), but down from 8.1% last time. Ask your doctor whether your plan needs any change.</p>
            </div>
            <div className="mt-3 flex items-center gap-3 rounded-2xl border border-line p-3 text-sm">
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-primary-100 font-semibold text-primary-800">P</span>
              <span className="flex-1">Priya (daughter) is connected</span>
              <span className="rounded-full bg-primary-100 px-2.5 py-0.5 text-[0.75rem] font-medium text-primary-800">Alerts on</span>
            </div>
          </div>
          <div className="absolute -bottom-5 -left-4 hidden rounded-2xl border border-line bg-surface px-4 py-3 text-sm shadow-soft sm:block">
            <span className="font-medium">“आपकी दोपहर की दवा का समय हो गया है।”</span>
          </div>
        </div>
      </section>

      <section className="border-y border-line bg-surface py-16">
        <div className="container">
          <h2 className="max-w-2xl text-3xl font-semibold tracking-tight">Everything an elderly patient or caregiver needs — without the paperwork.</h2>
          <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="rounded-2xl border border-line bg-background p-6">
                <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-secondary text-primary"><f.icon className="h-5 w-5" /></span>
                <h3 className="mt-4 text-lg font-semibold">{f.title}</h3>
                <p className="mt-1.5 text-[0.95rem] leading-relaxed text-ink-soft">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="container py-16">
        <div className="grid gap-10 lg:grid-cols-2">
          <div>
            <h2 className="text-3xl font-semibold tracking-tight">How it works</h2>
            <ol className="mt-8 space-y-6">
              {[["Upload", "Take a photo or upload a PDF of a prescription, report, diet chart or appointment slip."], ["Check", "We show what we read, how sure we are, and highlight anything unclear. You fix or confirm."],
                ["Relax", "Medicines, reminders, meal plans, appointments and your health history update automatically."]].map(([t, b], i) => (
                <li key={t} className="flex gap-4"><span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary font-semibold text-white">{i + 1}</span><div><div className="font-semibold">{t}</div><p className="text-ink-soft">{b}</p></div></li>
              ))}
            </ol>
          </div>
          <div className="rounded-3xl border border-line bg-surface p-8">
            <ShieldCheck className="h-8 w-8 text-primary" />
            <h3 className="mt-4 text-xl font-semibold">Built to be safe</h3>
            <ul className="mt-4 space-y-3 text-ink-soft">
              {["Never diagnoses, prescribes or changes a dose", "Never invents values or reference ranges", "Unclear prescriptions are flagged for your pharmacist or doctor", "Nothing is shared with family without your consent", "The AI can't send your data anywhere"].map((x) => (
                <li key={x} className="flex gap-2.5"><Check className="mt-1 h-4 w-4 shrink-0 text-primary" />{x}</li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="container pb-20">
        <div className="flex flex-col items-center gap-5 rounded-3xl bg-primary px-6 py-14 text-center text-white">
          <h2 className="text-3xl font-semibold tracking-tight">Start with one document.</h2>
          <p className="max-w-lg text-white/85">Upload a prescription or report and see how much simpler your health routine can be.</p>
          <Link href="/register" className="inline-flex h-14 items-center gap-2 rounded-2xl bg-white px-7 font-medium text-primary-800 hover:bg-primary-50"><Upload className="h-5 w-5" /> Get started free</Link>
        </div>
      </section>

      <footer className="border-t border-line py-8">
        <div className="container flex flex-col items-center justify-between gap-3 text-sm text-muted sm:flex-row">
          <Logo />
          <p>HealthMate AI provides information, not medical advice. In an emergency call 112.</p>
        </div>
      </footer>
    </div>
  );
}
