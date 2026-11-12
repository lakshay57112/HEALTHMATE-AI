"use client";
import Link from "next/link";
import { useState } from "react";
import { AlertTriangle, Bell, BellRing, CalendarClock, CheckCheck, FileText, Package, Pill, Settings2, Users } from "lucide-react";
import { toast } from "sonner";
import { EmptyState, ErrorState, LoadingGrid, PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, Segmented } from "@/components/ui/primitives";
import { api, useApi } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn, fmtDateTime } from "@/lib/utils";

const ICON: Record<string, any> = { medicine_due: Pill, medicine_missed: AlertTriangle, refill: Package, appointment: CalendarClock, document: FileText, caregiver: Users, system: Bell };

export default function NotificationsPage() {
  const { t } = useI18n();
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const { data, error, loading, reload } = useApi<any>(`/notifications?limit=100${filter === "unread" ? "&unread=true" : ""}`, [filter]);
  const open = async (n: any) => {
    if (!n.read) await api(`/notifications/${n.id}/read`, { method: "POST" }).catch(() => {});
  };
  return (
    <>
      <PageHeader title={t("Notifications")} description="Reminders, alerts and updates."
        actions={<>
          <Button asChild variant="outline"><Link href="/app/settings/reminders"><Settings2 /> Preferences</Link></Button>
          <Button variant="outline" onClick={async () => { const d = await api("/notifications/test", { method: "POST" }); toast.success(`Test sent · push: ${d.push_status}`); reload(); }}><BellRing /> Send test</Button>
          <Button onClick={async () => { await api("/notifications/read-all", { method: "POST" }); reload(); }}><CheckCheck /> Mark all read</Button>
        </>} />
      <Segmented className="mb-4" value={filter} onChange={setFilter} options={[{ value: "all", label: "All" }, { value: "unread", label: `Unread${data?.unread ? ` (${data.unread})` : ""}` }]} />
      {error ? <ErrorState message={error.message} onRetry={reload} /> : loading ? <LoadingGrid rows={3} className="lg:grid-cols-1 sm:grid-cols-1" /> : !data?.items.length ? (
        <EmptyState icon={Bell} title="You're all caught up" description="Medicine reminders, refill alerts and appointment reminders will appear here." />
      ) : (
        <Card className="divide-y divide-line">
          {data.items.map((n: any) => {
            const Icon = ICON[n.kind] || (n.kind.startsWith("caregiver") ? Users : Bell);
            return (
              <Link key={n.id} href={n.data?.url || "#"} onClick={() => open(n)} className={cn("flex items-start gap-3 px-5 py-4 hover:bg-background", !n.read && "bg-primary-50/40")}>
                <span className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl", n.severity === "warning" ? "bg-warning-bg text-warning-ink" : n.severity === "critical" ? "bg-danger-bg text-danger" : "bg-secondary text-primary")}><Icon className="h-5 w-5" /></span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2"><span className={cn("font-medium", !n.read && "font-semibold")}>{n.title}</span>{!n.read && <span className="h-2 w-2 rounded-full bg-primary" />}</div>
                  <p className="text-sm text-ink-soft">{n.body}</p>
                  <div className="mt-1 text-[0.75rem] text-muted">{fmtDateTime(n.created_at)}{n.push_status && n.push_status !== "none" ? ` · push: ${n.push_status.replace("_", " ")}` : ""}</div>
                </div>
              </Link>
            );
          })}
        </Card>
      )}
    </>
  );
}
