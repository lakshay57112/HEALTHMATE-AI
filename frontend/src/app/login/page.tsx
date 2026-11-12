"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { AuthLayout } from "@/components/auth-layout";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DemoButton } from "../demo-button";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { setUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email || !password) return setError("Enter your email and password");
    setBusy(true);
    try {
      const d = await api("/auth/login", { method: "POST", json: { email, password } });
      setUser(d.user);
      const next = params.get("next") || "";
      if (next.startsWith("/invite/")) router.push(next);
      else router.push(d.user.role === "caregiver" ? "/caregiver" : next.startsWith("/app") ? next : "/app");
    } catch (err: any) {
      setError(err.message);
      setBusy(false);
    }
  };
  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to see your medicines, reports and reminders." footer={<>New to HealthMate? <Link href="/register" className="font-medium text-primary">Create an account</Link></>}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <Field label="Email" htmlFor="email"><Input id="email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Field label="Password" htmlFor="password">
          <div className="relative">
            <Input id="password" type={show ? "text" : "password"} autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} className="pr-12" />
            <button type="button" onClick={() => setShow((s) => !s)} className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-2 text-muted hover:text-ink" aria-label={show ? "Hide password" : "Show password"}>{show ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}</button>
          </div>
        </Field>
        {error && <p className="rounded-xl bg-danger-bg px-4 py-3 text-sm text-danger-ink" role="alert">{error}</p>}
        <Button type="submit" size="xl" className="w-full" loading={busy}>Sign in</Button>
      </form>
      <div className="my-6 flex items-center gap-3 text-xs text-muted"><span className="h-px flex-1 bg-line" />or explore with sample data<span className="h-px flex-1 bg-line" /></div>
      <div className="grid gap-2 sm:grid-cols-2">
        <DemoButton className="h-12 text-sm" label="Demo patient" />
        <DemoButton role="caregiver" className="h-12 text-sm" label="Demo caregiver" />
      </div>
    </AuthLayout>
  );
}

export default function LoginPage() {
  return <Suspense><LoginForm /></Suspense>;
}
