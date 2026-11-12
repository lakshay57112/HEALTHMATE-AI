"use client";
import Link from "next/link";
import { AlertTriangle, ArrowLeft, FlaskConical, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge, Skeleton } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";

export function Logo({ className, compact }: { className?: string; compact?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5 font-semibold tracking-tight text-ink", className)}>
      <svg viewBox="0 0 64 64" className="h-8 w-8 shrink-0" aria-hidden>
        <rect width="64" height="64" rx="16" fill="#4D8B73" />
        <path d="M32 47s-14-8.6-14-19a8 8 0 0 1 14-5.3A8 8 0 0 1 46 28c0 10.4-14 19-14 19Z" fill="#fff" />
        <path d="M23 31h5l2.5-4 3.5 8 2.5-4H41" fill="none" stroke="#4D8B73" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {!compact && <span className="whitespace-nowrap text-[1.08rem]">HealthMate<span className="text-primary"> AI</span></span>}
    </span>
  );
}

export function PageHeader({ title, description, actions, back, eyebrow }: { title: React.ReactNode; description?: React.ReactNode; actions?: React.ReactNode; back?: string; eyebrow?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between animate-fade-up">
      <div className="min-w-0">
        {back && (
          <Link href={back} className="mb-3 inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
            <ArrowLeft className="h-4 w-4" /> Back
          </Link>
        )}
        {eyebrow && <div className="eyebrow mb-1.5">{eyebrow}</div>}
        <h1 className="text-[1.65rem] font-semibold leading-tight text-ink sm:text-[1.9rem]">{title}</h1>
        {description && <p className="mt-1.5 max-w-2xl text-[0.98rem] text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, description, action, className }: { icon: any; title: string; description?: string; action?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center rounded-2xl border border-dashed border-line-strong bg-surface/60 px-6 py-12 text-center", className)}>
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-secondary text-primary">
        <Icon className="h-6 w-6" />
      </div>
      <h3 className="text-base font-semibold">{title}</h3>
      {description && <p className="mt-1.5 max-w-sm text-sm text-muted">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-col items-center rounded-2xl border border-danger/20 bg-danger-bg/50 px-6 py-10 text-center">
      <AlertTriangle className="mb-3 h-6 w-6 text-danger" />
      <p className="text-sm text-danger-ink">{message || "Something went wrong."}</p>
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-4" onClick={onRetry}>
          <RefreshCw /> {t("Retry")}
        </Button>
      )}
    </div>
  );
}

export function LoadingGrid({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("grid gap-4 sm:grid-cols-2 lg:grid-cols-3", className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-36" />
      ))}
    </div>
  );
}

export function SampleBadge({ className }: { className?: string }) {
  const { t } = useI18n();
  return (
    <Badge variant="info" className={className} title="Generated demo values — not real readings">
      <FlaskConical /> {t("Sample data")}
    </Badge>
  );
}

const STATUS_STYLE: Record<string, { label: string; cls: string }> = {
  taken: { label: "Taken", cls: "bg-primary-100 text-primary-800" },
  skipped: { label: "Skipped", cls: "bg-muted-bg text-ink-soft" },
  missed: { label: "Missed", cls: "bg-danger-bg text-danger-ink" },
  overdue: { label: "Not confirmed", cls: "bg-warning-bg text-warning-ink" },
  due: { label: "Due now", cls: "bg-warning text-white" },
  upcoming: { label: "Upcoming", cls: "bg-muted-bg text-muted" },
  snoozed: { label: "Snoozed", cls: "bg-info-bg text-[#3D5F8F]" },
  high: { label: "High", cls: "bg-danger-bg text-danger-ink" },
  low: { label: "Low", cls: "bg-warning-bg text-warning-ink" },
  normal: { label: "Normal", cls: "bg-primary-100 text-primary-800" },
  unknown: { label: "No range", cls: "bg-muted-bg text-muted" },
};

export function StatusPill({ status, className }: { status: string; className?: string }) {
  const { t } = useI18n();
  const s = STATUS_STYLE[status] || { label: status, cls: "bg-muted-bg text-muted" };
  return <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-[0.78rem] font-medium", s.cls, className)}>{t(s.label)}</span>;
}

export function IconTile({ icon: Icon, tone = "primary", className }: { icon: any; tone?: "primary" | "warning" | "danger" | "info" | "muted"; className?: string }) {
  const tones = { primary: "bg-secondary text-primary", warning: "bg-warning-bg text-warning-ink", danger: "bg-danger-bg text-danger", info: "bg-info-bg text-info", muted: "bg-muted-bg text-muted" };
  return (
    <span className={cn("inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl", tones[tone], className)}>
      <Icon className="h-5 w-5" />
    </span>
  );
}

export function Disclaimer({ className, children }: { className?: string; children?: React.ReactNode }) {
  return (
    <p className={cn("rounded-xl bg-muted-bg px-4 py-3 text-[0.85rem] leading-relaxed text-ink-soft", className)}>
      {children || "HealthMate explains your information in simple language. It does not diagnose conditions or change prescriptions. Always follow your doctor's advice."}
    </p>
  );
}
