"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { HeartHandshake, User } from "lucide-react";
import { z } from "zod";
import { AuthLayout } from "@/components/auth-layout";
import { Button } from "@/components/ui/button";
import { Checkbox, Field, Input, Segmented } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const schema = z.object({
  full_name: z.string().trim().min(2, "Please enter your full name"),
  email: z.string().trim().email("Enter a valid email address"),
  password: z.string().min(8, "Use at least 8 characters"),
  accept_terms: z.literal(true, { message: "Please accept to continue" }),
});

function RegisterForm() {
  const router = useRouter();
  const params = useSearchParams();
  const invite = params.get("invite");
  const { setUser } = useAuth();
  const { lang, setLang } = useI18n();
  const [role, setRole] = useState<"patient" | "caregiver">(invite ? "caregiver" : "patient");
  const [f, setF] = useState({ full_name: "", email: params.get("email") || "", password: "", accept_terms: false });
  const [errs, setErrs] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const r = schema.safeParse(f);
    if (!r.success) {
      setErrs(Object.fromEntries(r.error.issues.map((i) => [String(i.path[0]), i.message])));
      return;
    }
    setErrs({});
    setBusy(true);
    try {
      const d = await api("/auth/register", { method: "POST", json: { ...f, role, language: lang, invite_token: invite } });
      setUser(d.user);
      router.push(role === "caregiver" ? "/caregiver" : "/onboarding");
    } catch (err: any) {
      setError(err.message);
      setBusy(false);
    }
  };
  return (
    <AuthLayout title={invite ? "Accept your invitation" : "Create your account"} subtitle={invite ? "Create a caregiver account to connect with your family member." : "It takes a minute. You can add documents right after."}
      footer={<>Already have an account? <Link href={`/login${invite ? `?next=/invite/${invite}` : ""}`} className="font-medium text-primary">Sign in</Link></>}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        {!invite && (
          <div className="grid grid-cols-2 gap-2">
            {([["patient", User, "For myself", "Manage my health"], ["caregiver", HeartHandshake, "Caregiver", "Support a family member"]] as const).map(([v, Icon, t, d]) => (
              <button key={v} type="button" onClick={() => setRole(v)} aria-pressed={role === v} className={cn("rounded-2xl border p-4 text-left transition-all", role === v ? "border-primary ring-4 ring-primary/10" : "border-line hover:border-primary-300")}>
                <Icon className={cn("h-5 w-5", role === v ? "text-primary" : "text-muted")} /><div className="mt-2 font-semibold">{t}</div><div className="text-[0.8rem] text-muted">{d}</div>
              </button>
            ))}
          </div>
        )}
        <Field label="Full name" error={errs.full_name}><Input autoComplete="name" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} aria-invalid={!!errs.full_name} /></Field>
        <Field label="Email" error={errs.email}><Input type="email" autoComplete="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} aria-invalid={!!errs.email} /></Field>
        <Field label="Password" error={errs.password} hint="At least 8 characters"><Input type="password" autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} aria-invalid={!!errs.password} /></Field>
        <Field label="Preferred language"><Segmented value={lang} onChange={setLang} options={[{ value: "en", label: "English" }, { value: "hi", label: "हिंदी" }]} /></Field>
        <label className="flex items-start gap-3 text-sm text-ink-soft"><Checkbox checked={f.accept_terms} onCheckedChange={(v) => setF({ ...f, accept_terms: !!v })} className="mt-0.5" /><span>I agree to the terms and privacy policy. I understand HealthMate gives information, not medical advice.</span></label>
        {errs.accept_terms && <p className="text-sm text-danger-ink">{errs.accept_terms}</p>}
        {error && <p className="rounded-xl bg-danger-bg px-4 py-3 text-sm text-danger-ink" role="alert">{error}</p>}
        <Button type="submit" size="xl" className="w-full" loading={busy}>Create account</Button>
      </form>
    </AuthLayout>
  );
}

export default function RegisterPage() {
  return <Suspense><RegisterForm /></Suspense>;
}
