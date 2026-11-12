"use client";
import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardContent, CardHeader, CardTitle, Field, Input, NativeSelect } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { initials } from "@/lib/utils";
import { TagInput } from "@/components/tag-input";

export default function ProfilePage() {
  const { user, setUser } = useAuth();
  const [f, setF] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (user) setF({ full_name: user.full_name, ...user.profile }); }, [user]);
  if (!f) return null;
  const set = (k: string, v: any) => setF((p: any) => ({ ...p, [k]: v }));
  const save = async () => {
    setBusy(true);
    try {
      const body: any = {};
      for (const k of ["full_name", "date_of_birth", "gender", "phone", "blood_group", "height_cm", "weight_kg", "conditions", "allergies", "food_preference", "activity_level", "budget_preference", "emergency_contact_name", "emergency_contact_phone"]) {
        body[k] = f[k] === "" ? null : f[k];
      }
      body.height_cm = body.height_cm ? +body.height_cm : null;
      body.weight_kg = body.weight_kg ? +body.weight_kg : null;
      const d = await api("/profile", { method: "PUT", json: body });
      setUser(d.user);
      toast.success("Profile saved");
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <PageHeader title="Your profile" description="Only information you confirm is used by HealthMate. Conditions are never guessed by the AI." actions={<Button onClick={save} loading={busy}><Save /> Save changes</Button>} />
      <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
        <Card className="h-fit p-6 text-center">
          <span className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-primary-100 text-2xl font-semibold text-primary-800">{initials(user?.full_name)}</span>
          <div className="mt-3 text-lg font-semibold">{user?.full_name}</div>
          <div className="text-sm text-muted">{user?.email}</div>
          {user?.is_demo && <Badge variant="info" className="mt-3">Demo account</Badge>}
        </Card>
        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle>Personal details</CardTitle></CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <Field label="Full name"><Input value={f.full_name || ""} onChange={(e) => set("full_name", e.target.value)} /></Field>
              <Field label="Date of birth"><Input type="date" value={f.date_of_birth || ""} onChange={(e) => set("date_of_birth", e.target.value)} /></Field>
              <Field label="Gender"><NativeSelect value={f.gender || ""} onChange={(e) => set("gender", e.target.value || null)}><option value="">Prefer not to say</option><option value="female">Female</option><option value="male">Male</option><option value="other">Other</option></NativeSelect></Field>
              <Field label="Phone"><Input value={f.phone || ""} onChange={(e) => set("phone", e.target.value)} /></Field>
              <Field label="Blood group"><NativeSelect value={f.blood_group || ""} onChange={(e) => set("blood_group", e.target.value)}><option value="">—</option>{["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map((b) => <option key={b}>{b}</option>)}</NativeSelect></Field>
              <div className="grid grid-cols-2 gap-3"><Field label="Height (cm)"><Input type="number" value={f.height_cm ?? ""} onChange={(e) => set("height_cm", e.target.value)} /></Field><Field label="Weight (kg)"><Input type="number" value={f.weight_kg ?? ""} onChange={(e) => set("weight_kg", e.target.value)} /></Field></div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Health information</CardTitle></CardHeader>
            <CardContent className="space-y-5">
              <Field label="Conditions (confirmed by your doctor)" hint="Press Enter to add"><TagInput value={f.conditions || []} onChange={(v) => set("conditions", v)} placeholder="e.g. Type 2 diabetes" suggestions={["Type 2 diabetes", "Hypertension", "High cholesterol", "Hypothyroidism", "Kidney disease", "Heart disease", "Gout"]} /></Field>
              <Field label="Food allergies"><TagInput value={f.allergies || []} onChange={(v) => set("allergies", v)} placeholder="e.g. Peanuts" suggestions={["Peanuts", "Milk", "Gluten", "Egg", "Soy", "Fish"]} /></Field>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Food preference"><NativeSelect value={f.food_preference} onChange={(e) => set("food_preference", e.target.value)}><option value="vegetarian">Vegetarian</option><option value="eggetarian">Eggetarian</option><option value="non_vegetarian">Non-vegetarian</option><option value="vegan">Vegan</option></NativeSelect></Field>
                <Field label="Activity level"><NativeSelect value={f.activity_level} onChange={(e) => set("activity_level", e.target.value)}><option value="sedentary">Mostly sitting</option><option value="light">Light (short walks)</option><option value="moderate">Moderate</option><option value="active">Active</option></NativeSelect></Field>
                <Field label="Food budget"><NativeSelect value={f.budget_preference} onChange={(e) => set("budget_preference", e.target.value)}><option value="low">Budget</option><option value="moderate">Moderate</option><option value="high">Flexible</option></NativeSelect></Field>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Emergency contact</CardTitle></CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <Field label="Name"><Input value={f.emergency_contact_name || ""} onChange={(e) => set("emergency_contact_name", e.target.value)} /></Field>
              <Field label="Phone"><Input value={f.emergency_contact_phone || ""} onChange={(e) => set("emergency_contact_phone", e.target.value)} /></Field>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
