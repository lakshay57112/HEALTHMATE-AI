"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { Check, HeartHandshake, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { AuthLayout } from "@/components/auth-layout";
import { Button } from "@/components/ui/button";
import { api, useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function InvitePage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const { user, loading } = useAuth();
  const info = useApi<any>(`/invitations/${token}`);
  const [busy, setBusy] = useState(false);
  const accept = async () => {
    setBusy(true);
    try {
      await api(`/invitations/${token}/accept`, { method: "POST" });
      toast.success("You're connected");
      router.push("/caregiver");
    } catch (e: any) {
      toast.error(e.message);
      setBusy(false);
    }
  };
  if (info.loading || loading) return <div className="flex min-h-screen items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-muted" /></div>;
  if (info.error) return <AuthLayout title="Invitation not found" subtitle="This link may have expired or already been used. Ask your family member to send a new one."><Button asChild><Link href="/">Go home</Link></Button></AuthLayout>;
  const d = info.data;
  return (
    <AuthLayout title={`${d.patient_first_name} invited you`} subtitle={`to be their ${d.relationship} on HealthMate.`}>
      <div className="rounded-2xl border border-line bg-surface p-5">
        <div className="flex items-center gap-2 font-semibold"><HeartHandshake className="h-5 w-5 text-primary" /> You&apos;ll be able to</div>
        <ul className="mt-3 space-y-2 text-[0.95rem] text-ink-soft">{d.permissions.map((p: string) => <li key={p} className="flex gap-2"><Check className="mt-1 h-4 w-4 text-primary" />{p}</li>)}</ul>
        <p className="mt-4 text-[0.82rem] text-muted">{d.patient_first_name} can change or remove this access at any time.</p>
      </div>
      <div className="mt-6 space-y-2">
        {user?.role === "caregiver" ? (
          <Button size="xl" className="w-full" onClick={accept} loading={busy}>Accept invitation</Button>
        ) : user ? (
          <p className="rounded-xl bg-warning-bg px-4 py-3 text-sm text-warning-ink">You&apos;re signed in as a patient. Please sign out and use a caregiver account to accept.</p>
        ) : (
          <>
            <Button asChild size="xl" className="w-full"><Link href={`/register?invite=${token}&email=${encodeURIComponent(d.invite_email)}`}>Create caregiver account</Link></Button>
            <Button asChild variant="outline" size="xl" className="w-full"><Link href={`/login?next=/invite/${token}`}>I already have an account</Link></Button>
          </>
        )}
      </div>
    </AuthLayout>
  );
}
