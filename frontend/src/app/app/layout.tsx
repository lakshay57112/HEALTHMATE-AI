"use client";
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const { setLang } = useI18n();
  const router = useRouter();
  const path = usePathname();

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace(`/login?next=${encodeURIComponent(path)}`);
    else if (user.role === "caregiver") router.replace("/caregiver");
    else if (!user.profile?.onboarding_complete) router.replace("/onboarding");
  }, [user, loading, router, path]);

  useEffect(() => {
    if (user?.language) setLang(user.language);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.language]);

  if (loading || !user || user.role !== "patient" || !user.profile?.onboarding_complete) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }
  return <AppShell>{children}</AppShell>;
}
