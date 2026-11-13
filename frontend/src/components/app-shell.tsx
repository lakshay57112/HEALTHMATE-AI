"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  Bell, CalendarClock, FileText, History, House, Languages, LogOut, Menu, Pill, Plus, Salad, Settings, Sparkles, Square, User as UserIcon, Users, Volume2, X,
} from "lucide-react";
import { Logo } from "@/components/common";
import { ReminderAgent } from "@/components/reminder-agent";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { cn, initials } from "@/lib/utils";
import { stopSpeaking, useSpeaking } from "@/lib/voice";

const NAV = [
  { href: "/app", label: "Overview", icon: House },
  { href: "/app/reports", label: "Medical Reports", icon: FileText },
  { href: "/app/medicines", label: "Medicines", icon: Pill },
  { href: "/app/nutrition", label: "Nutrition", icon: Salad },
  { href: "/app/appointments", label: "Appointments", icon: CalendarClock },
  { href: "/app/history", label: "Health History", icon: History },
  { href: "/app/family", label: "Family & Caretakers", icon: Users },
  { href: "/app/assistant", label: "AI Health Assistant", icon: Sparkles },
  { href: "/app/settings", label: "Settings", icon: Settings },
];
const MOBILE = [
  { href: "/app", label: "Home", icon: House },
  { href: "/app/medicines", label: "Medicines", icon: Pill },
  { href: "/app/documents/new", label: "Add", icon: Plus, primary: true },
  { href: "/app/assistant", label: "Assistant", icon: Sparkles },
];

function isActive(path: string, href: string) {
  return href === "/app" ? path === "/app" : path.startsWith(href);
}

export function LanguageToggle({ className }: { className?: string }) {
  const { lang, setLang } = useI18n();
  const { user, setUser } = useAuth();
  const toggle = async () => {
    const next = lang === "en" ? "hi" : "en";
    setLang(next);
    if (user) {
      try {
        const d = await api("/profile", { method: "PUT", json: { language: next } });
        setUser(d.user);
      } catch {}
    }
  };
  return (
    <button onClick={toggle} className={cn("inline-flex h-10 items-center gap-1.5 rounded-xl px-3 text-sm font-medium text-ink-soft hover:bg-muted-bg", className)} aria-label="Switch language">
      <Languages className="h-4 w-4" />
      <span className={lang === "en" ? "text-ink" : "text-muted"}>EN</span>
      <span className="text-line-strong">/</span>
      <span className={lang === "hi" ? "text-ink" : "text-muted"}>हिं</span>
    </button>
  );
}

function NotificationBell() {
  const [count, setCount] = useState(0);
  const path = usePathname();
  useEffect(() => {
    let alive = true;
    const load = () => api("/notifications?unread=true&limit=1").then((d) => alive && setCount(d.unread)).catch(() => {});
    load();
    const id = setInterval(load, 60000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [path]);
  return (
    <Link href="/app/notifications" className="relative inline-flex h-10 w-10 items-center justify-center rounded-xl text-ink-soft hover:bg-muted-bg" aria-label={`Notifications${count ? `, ${count} unread` : ""}`}>
      <Bell className="h-5 w-5" />
      {count > 0 && <span className="absolute right-1.5 top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[0.65rem] font-semibold text-white">{count > 9 ? "9+" : count}</span>}
    </Link>
  );
}

function UserMenu() {
  const { user, logout } = useAuth();
  const { t } = useI18n();
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger className="flex h-10 items-center gap-2 rounded-xl pl-1 pr-2 hover:bg-muted-bg" aria-label="Account menu">
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-100 text-sm font-semibold text-primary-800">{initials(user?.full_name)}</span>
        <span className="hidden text-sm font-medium lg:inline">{user?.full_name.split(" ")[0]}</span>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align="end" sideOffset={8} className="z-50 min-w-[220px] rounded-2xl border border-line bg-surface p-1.5 shadow-lift">
          <div className="px-3 py-2">
            <div className="text-sm font-semibold">{user?.full_name}</div>
            <div className="truncate text-xs text-muted">{user?.email}</div>
          </div>
          <DropdownMenu.Separator className="my-1 h-px bg-line" />
          {[{ href: "/app/profile", label: "Profile", icon: UserIcon }, { href: "/app/notifications", label: "Notifications", icon: Bell }, { href: "/app/settings", label: "Settings", icon: Settings }].map((i) => (
            <DropdownMenu.Item key={i.href} asChild>
              <Link href={i.href} className="flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm outline-none data-[highlighted]:bg-muted-bg">
                <i.icon className="h-4 w-4 text-muted" /> {t(i.label)}
              </Link>
            </DropdownMenu.Item>
          ))}
          <DropdownMenu.Separator className="my-1 h-px bg-line" />
          <DropdownMenu.Item onSelect={logout} className="flex cursor-pointer items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm text-danger-ink outline-none data-[highlighted]:bg-danger-bg">
            <LogOut className="h-4 w-4" /> {t("Sign out")}
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

/** Floating control shown on every screen while something is being read aloud. */
function StopSpeakingPill() {
  const speaking = useSpeaking();
  if (!speaking) return null;
  return (
    <div className="fixed inset-x-0 bottom-24 z-50 flex justify-center px-4 lg:bottom-6 lg:ml-[264px]" role="status" aria-live="polite">
      <div className="flex items-center gap-3 rounded-full bg-ink py-1.5 pl-4 pr-1.5 text-sm text-white shadow-lift animate-fade-up">
        <Volume2 className="h-4 w-4 animate-pulse" aria-hidden />
        <span>Reading aloud…</span>
        <button onClick={stopSpeaking} className="inline-flex h-9 items-center gap-1.5 rounded-full bg-white px-3.5 font-medium text-ink hover:bg-white/90">
          <Square className="h-3.5 w-3.5 fill-current" /> Stop
        </button>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { t } = useI18n();
  const { user } = useAuth();
  const [moreOpen, setMoreOpen] = useState(false);
  useEffect(() => {
    setMoreOpen(false);
    stopSpeaking(); // leaving a screen stops anything it was reading aloud
  }, [path]);
  useEffect(() => {
    const stop = () => {
      stopSpeaking();
    };
    window.addEventListener("pagehide", stop);
    return () => {
      window.removeEventListener("pagehide", stop);
      stopSpeaking();
    };
  }, []);

  return (
    <div className="min-h-screen">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[264px] flex-col border-r border-line bg-surface/80 backdrop-blur lg:flex">
        <div className="flex h-16 items-center px-6">
          <Link href="/app"><Logo /></Link>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-3" aria-label="Main">
          {NAV.map((n) => {
            const active = isActive(path, n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                className={cn(
                  "group flex h-11 items-center gap-3 rounded-xl px-3 text-[0.95rem] font-medium text-ink-soft transition-colors hover:bg-muted-bg hover:text-ink",
                  active && "bg-secondary text-primary-800 hover:bg-secondary",
                )}
                aria-current={active ? "page" : undefined}
              >
                <n.icon className={cn("h-[1.15rem] w-[1.15rem] text-muted group-hover:text-ink-soft", active && "text-primary")} />
                {t(n.label)}
              </Link>
            );
          })}
        </nav>
        <div className="m-3 rounded-2xl border border-line bg-background p-4">
          <div className="text-sm font-semibold">{t("Upload a document")}</div>
          <p className="mt-1 text-[0.82rem] leading-snug text-muted">Prescription, report or doctor&apos;s note — we&apos;ll read it for you.</p>
          <Link href="/app/documents/new" className="mt-3 inline-flex h-9 items-center gap-1.5 rounded-lg bg-primary px-3 text-sm font-medium text-white hover:bg-primary-600">
            <Plus className="h-4 w-4" /> Upload
          </Link>
        </div>
      </aside>

      {/* Top bar */}
      <header className="sticky top-0 z-20 border-b border-line bg-background/85 backdrop-blur lg:ml-[264px]">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
          <Link href="/app" className="lg:hidden"><Logo /></Link>
          <div className="hidden text-sm text-muted lg:block">{user?.is_demo && <span className="rounded-full bg-info-bg px-2.5 py-1 text-[0.78rem] font-medium text-[#3D5F8F]">Demo account · sample data</span>}</div>
          <div className="flex items-center gap-1">
            <LanguageToggle />
            <NotificationBell />
            <UserMenu />
          </div>
        </div>
      </header>

      <main className="lg:ml-[264px]">
        <div className="mx-auto max-w-6xl px-4 pb-28 pt-6 sm:px-6 lg:pb-12 lg:pt-8">{children}</div>
      </main>

      <StopSpeakingPill />

      {/* Mobile bottom navigation */}
      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden" aria-label="Mobile">
        <div className="mx-auto grid max-w-md grid-cols-5">
          {MOBILE.map((n) => {
            const active = isActive(path, n.href);
            return n.primary ? (
              <Link key={n.href} href={n.href} className="flex flex-col items-center justify-center py-2" aria-label="Upload document">
                <span className="-mt-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-white shadow-lift"><n.icon className="h-6 w-6" /></span>
              </Link>
            ) : (
              <Link key={n.href} href={n.href} className={cn("flex h-16 flex-col items-center justify-center gap-1 text-[0.72rem] font-medium text-muted", active && "text-primary")}>
                <n.icon className="h-[1.35rem] w-[1.35rem]" />
                {t(n.label)}
              </Link>
            );
          })}
          <button onClick={() => setMoreOpen(true)} className="flex h-16 flex-col items-center justify-center gap-1 text-[0.72rem] font-medium text-muted">
            <Menu className="h-[1.35rem] w-[1.35rem]" />
            {t("More")}
          </button>
        </div>
      </nav>
      {moreOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-ink/30" onClick={() => setMoreOpen(false)} />
          <div className="absolute inset-x-0 bottom-0 rounded-t-3xl bg-surface p-4 pb-8 shadow-lift animate-fade-up">
            <div className="mb-2 flex items-center justify-between px-2">
              <span className="font-semibold">{t("More")}</span>
              <button onClick={() => setMoreOpen(false)} className="rounded-lg p-2 hover:bg-muted-bg" aria-label="Close"><X className="h-5 w-5" /></button>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {NAV.filter((n) => !["/app", "/app/medicines", "/app/assistant"].includes(n.href)).map((n) => (
                <Link key={n.href} href={n.href} className="flex flex-col items-center gap-2 rounded-2xl border border-line p-4 text-center text-[0.8rem] font-medium">
                  <n.icon className="h-6 w-6 text-primary" />
                  {t(n.label)}
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}
      <ReminderAgent />
    </div>
  );
}
