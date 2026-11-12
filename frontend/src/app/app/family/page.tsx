"use client";
import { useState } from "react";
import { Check, Copy, Link2, Mail, Phone, ShieldCheck, Siren, Trash2, UserPlus, Users } from "lucide-react";
import { toast } from "sonner";
import { EmptyState, ErrorState, LoadingGrid, PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Badge, Card, Checkbox, Field, Input, NativeSelect, Switch } from "@/components/ui/primitives";
import { api, useApi } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { RELATIONSHIPS, cn, fmtDate, initials } from "@/lib/utils";

const DEFAULTS: Record<string, boolean> = { view_medicines: true, missed_medicine_alerts: true, adherence_summary: true, view_appointments: true, appointment_alerts: true, view_reports: false, view_measurements: false, daily_summary: true, view_nutrition: false };

function PermissionList({ labels, value, onChange }: { labels: Record<string, string>; value: Record<string, boolean>; onChange: (v: Record<string, boolean>) => void }) {
  return (
    <div className="divide-y divide-line rounded-2xl border border-line">
      {Object.entries(labels).map(([k, label]) => (
        <label key={k} className="flex cursor-pointer items-center justify-between gap-4 px-4 py-3 text-[0.95rem]">
          <span>{label}</span>
          <Switch checked={!!value[k]} onCheckedChange={(v) => onChange({ ...value, [k]: v })} aria-label={label} />
        </label>
      ))}
    </div>
  );
}

function InviteDialog({ open, onOpenChange, labels, onDone }: { open: boolean; onOpenChange: (o: boolean) => void; labels: Record<string, string>; onDone: () => void }) {
  const [f, setF] = useState<any>({ name: "", email: "", relationship: "daughter", phone: "", escalation_minutes: 30, is_emergency_contact: false });
  const [perms, setPerms] = useState(DEFAULTS);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [link, setLink] = useState<string | null>(null);
  const [errs, setErrs] = useState<Record<string, string>>({});
  const submit = async () => {
    const e: Record<string, string> = {};
    if (f.name.trim().length < 2) e.name = "Enter their name";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.email)) e.email = "Enter a valid email";
    setErrs(e);
    if (Object.keys(e).length) return;
    setBusy(true);
    try {
      const d = await api("/family/invite", { method: "POST", json: { ...f, phone: f.phone || null, permissions: perms, consent } });
      setLink(d.invite_link);
      onDone();
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  };
  const close = (o: boolean) => {
    onOpenChange(o);
    if (!o) setTimeout(() => { setLink(null); setConsent(false); setF({ name: "", email: "", relationship: "daughter", phone: "", escalation_minutes: 30, is_emergency_contact: false }); setPerms(DEFAULTS); }, 200);
  };
  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent title={link ? "Invitation ready" : "Invite a family member"} description={link ? undefined : "They'll only see what you choose below. You can change this any time."} wide>
        {link ? (
          <div className="space-y-4">
            <div className="flex items-center gap-3 rounded-2xl bg-secondary p-4 text-primary-800"><Check className="h-5 w-5" /> Share this link with {f.name}. It works for 7 days.</div>
            <div className="flex gap-2"><Input readOnly value={link} className="font-mono text-sm" /><Button onClick={() => { navigator.clipboard.writeText(link); toast.success("Link copied"); }}><Copy /> Copy</Button></div>
            <div className="flex flex-wrap gap-2">
              <Button asChild variant="outline"><a href={`https://wa.me/?text=${encodeURIComponent(`Please join me on HealthMate AI: ${link}`)}`} target="_blank" rel="noreferrer">Share on WhatsApp</a></Button>
              <Button asChild variant="outline"><a href={`mailto:${f.email}?subject=${encodeURIComponent("Join me on HealthMate AI")}&body=${encodeURIComponent(link)}`}><Mail /> Email</a></Button>
            </div>
            <p className="text-[0.82rem] text-muted">Email delivery isn&apos;t set up on this server, so please send the link yourself.</p>
          </div>
        ) : (
          <div className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Name" error={errs.name}><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
              <Field label="Relationship"><NativeSelect value={f.relationship} onChange={(e) => setF({ ...f, relationship: e.target.value })}>{RELATIONSHIPS.map((r) => <option key={r} value={r} className="capitalize">{r === "family" ? "Family member" : r.charAt(0).toUpperCase() + r.slice(1)}</option>)}</NativeSelect></Field>
              <Field label="Email" error={errs.email}><Input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
              <Field label="Phone (optional)"><Input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
            </div>
            <div>
              <div className="mb-2 text-sm font-medium text-ink-soft">What can they see?</div>
              <PermissionList labels={labels} value={perms} onChange={setPerms} />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Alert them if a medicine isn't confirmed within"><NativeSelect value={f.escalation_minutes} onChange={(e) => setF({ ...f, escalation_minutes: +e.target.value })}>{[15, 30, 45, 60, 120].map((m) => <option key={m} value={m}>{m} minutes</option>)}</NativeSelect></Field>
              <label className="flex items-center gap-3 self-end pb-3 text-sm"><Switch checked={f.is_emergency_contact} onCheckedChange={(v) => setF({ ...f, is_emergency_contact: v })} /> Emergency contact</label>
            </div>
            <label className="flex items-start gap-3 rounded-2xl bg-background p-4 text-sm"><Checkbox checked={consent} onCheckedChange={(v) => setConsent(!!v)} className="mt-0.5" /><span>I agree to share the information selected above with this person. I can change or withdraw this at any time.</span></label>
            <div className="flex justify-end gap-2"><Button variant="outline" onClick={() => close(false)}>Cancel</Button><Button disabled={!consent} loading={busy} onClick={submit}><UserPlus /> Create invitation</Button></div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function FamilyPage() {
  const { t } = useI18n();
  const { data, error, loading, reload } = useApi<any>("/family");
  const [invite, setInvite] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [perms, setPerms] = useState<Record<string, boolean>>({});

  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  const items = data?.items || [];
  const savePerms = async (id: string) => {
    await api(`/family/${id}/permissions`, { method: "PUT", json: { permissions: perms } });
    toast.success("Permissions updated");
    setEditing(null);
    reload();
  };
  const revoke = async (c: any) => {
    if (!confirm(`Remove ${c.name}'s access? They will stop receiving any information immediately.`)) return;
    await api(`/family/${c.id}`, { method: "DELETE" });
    toast.success("Access removed");
    reload();
  };
  const resend = async (c: any) => {
    const d = await api(`/family/${c.id}/resend`, { method: "POST" });
    navigator.clipboard.writeText(d.invite_link).catch(() => {});
    toast.success("New invite link copied");
  };

  return (
    <>
      <PageHeader title={t("Family & Caretakers")} description={`Up to ${data?.max || 3} trusted people can be alerted if you miss a medicine. You decide exactly what each person sees.`}
        actions={items.length < (data?.max || 3) && <Button onClick={() => setInvite(true)}><UserPlus /> {t("Add family member")}</Button>} />
      <Card className="mb-6 flex items-start gap-3 p-4 text-sm text-ink-soft"><ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" />Nothing is shared without your consent. Alerts are sent by the app&apos;s reminder system — never by the AI assistant. Every view by a caregiver is recorded in your activity log.</Card>
      {loading ? <LoadingGrid rows={2} /> : items.length === 0 ? (
        <EmptyState icon={Users} title="No one connected yet" description="Invite a son, daughter, spouse or caretaker. They'll get a gentle alert if a dose isn't confirmed." action={<Button onClick={() => setInvite(true)}>Invite someone</Button>} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {items.map((c: any) => (
            <Card key={c.id} className="p-5">
              <div className="flex items-start gap-3">
                <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-100 text-lg font-semibold text-primary-800">{initials(c.name)}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2"><span className="text-lg font-semibold">{c.name}</span>{c.is_emergency_contact && <Badge variant="danger"><Siren /> Emergency</Badge>}</div>
                  <div className="truncate text-sm text-muted"><span className="capitalize">{c.relationship}</span> · {c.invite_email}</div>
                  {c.phone && <a href={`tel:${c.phone}`} className="mt-0.5 flex items-center gap-1 text-sm text-primary"><Phone className="h-3.5 w-3.5" />{c.phone}</a>}
                </div>
                <Badge className="shrink-0" variant={c.status === "active" ? "success" : "warning"}>{c.status === "active" ? t("Connected") : t("Invite pending")}</Badge>
              </div>
              {editing === c.id ? (
                <div className="mt-4 space-y-3">
                  <PermissionList labels={data.permission_labels} value={perms} onChange={setPerms} />
                  <div className="flex justify-end gap-2"><Button variant="outline" size="sm" onClick={() => setEditing(null)}>Cancel</Button><Button size="sm" onClick={() => savePerms(c.id)}>Save</Button></div>
                </div>
              ) : (
                <div className="mt-4 flex flex-wrap gap-1.5">
                  {Object.entries(c.permissions).filter(([, v]) => v).map(([k]) => <Badge key={k} variant="outline">{data.permission_labels[k]}</Badge>)}
                </div>
              )}
              <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3 text-[0.82rem] text-muted">
                <span>{c.status === "active" ? `Connected ${fmtDate(c.accepted_at)} · alerts after ${c.escalation_minutes} min` : `Invited ${fmtDate(c.created_at)}`}{c.consent?.granted ? " · consent recorded" : ""}</span>
                <div className="flex gap-1">
                  {c.status === "pending" && <Button variant="ghost" size="sm" onClick={() => resend(c)}><Link2 /> New link</Button>}
                  {editing !== c.id && <Button variant="ghost" size="sm" onClick={() => { setEditing(c.id); setPerms(c.permissions); }}>Permissions</Button>}
                  <Button variant="ghost" size="icon-sm" onClick={() => revoke(c)} aria-label="Remove access"><Trash2 /></Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
      {data && <InviteDialog open={invite} onOpenChange={setInvite} labels={data.permission_labels} onDone={reload} />}
      <p className={cn("mt-6 text-[0.82rem] text-muted")}>Caregivers sign in with their own account and see a separate caregiver dashboard.</p>
    </>
  );
}
