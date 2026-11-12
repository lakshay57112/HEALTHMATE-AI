"use client";
import * as React from "react";
import * as LabelPrimitive from "@radix-ui/react-label";
import * as SwitchPrimitive from "@radix-ui/react-switch";
import * as ProgressPrimitive from "@radix-ui/react-progress";
import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

/* ---------------- Card ---------------- */
export function Card({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("card", className)} {...p} />;
}
export function CardHeader({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex items-start justify-between gap-3 px-5 pt-5", className)} {...p} />;
}
export function CardTitle({ className, ...p }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-[1.02rem] font-semibold text-ink", className)} {...p} />;
}
export function CardDescription({ className, ...p }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("mt-0.5 text-sm text-muted", className)} {...p} />;
}
export function CardContent({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 pb-5 pt-4", className)} {...p} />;
}

/* ---------------- Inputs ---------------- */
export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...p }, ref) => (
  <input
    ref={ref}
    className={cn(
      "flex h-12 w-full rounded-xl border border-input bg-surface px-3.5 text-[0.98rem] text-ink placeholder:text-muted/80 transition-colors focus:border-primary focus:outline-none focus:ring-4 focus:ring-primary/10 disabled:opacity-60 aria-[invalid=true]:border-danger",
      className,
    )}
    {...p}
  />
));
Input.displayName = "Input";

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...p }, ref) => (
  <textarea
    ref={ref}
    className={cn("flex min-h-[96px] w-full rounded-xl border border-input bg-surface px-3.5 py-3 text-[0.98rem] placeholder:text-muted/80 focus:border-primary focus:outline-none focus:ring-4 focus:ring-primary/10", className)}
    {...p}
  />
));
Textarea.displayName = "Textarea";

export const NativeSelect = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(({ className, children, ...p }, ref) => (
  <div className={cn("relative", className?.match(/\b(w-|sm:w-|max-w-)\S+/g)?.join(" "))}>
    <select
      ref={ref}
      className={cn(
        "h-12 w-full appearance-none rounded-xl border border-input bg-surface pl-3.5 pr-10 text-[0.98rem] text-ink focus:border-primary focus:outline-none focus:ring-4 focus:ring-primary/10 disabled:opacity-60",
        className,
      )}
      {...p}
    >
      {children}
    </select>
    <ChevronDown className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
  </div>
));
NativeSelect.displayName = "NativeSelect";

export function Label({ className, ...p }: React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>) {
  return <LabelPrimitive.Root className={cn("text-sm font-medium text-ink-soft", className)} {...p} />;
}

const LABELABLE = new Set(["input", "textarea", "select"]);
function isLabelable(el: React.ReactElement): boolean {
  const t = el.type as any;
  return (typeof t === "string" && LABELABLE.has(t)) || t === Input || t === Textarea || t === NativeSelect;
}

/** Form field: links the label, hint and error to the control for screen readers (and getByLabel in tests). */
export function Field({ label, hint, error, children, className, htmlFor }: { label?: React.ReactNode; hint?: React.ReactNode; error?: string | null; children: React.ReactNode; className?: string; htmlFor?: string }) {
  const auto = React.useId();
  const child = React.Children.count(children) === 1 && React.isValidElement(children) ? (children as React.ReactElement<any>) : null;
  const linkable = !!child && isLabelable(child);
  const id = htmlFor || child?.props?.id || (linkable ? auto : undefined);
  const msgId = `${auto}-msg`;
  const control = linkable && child
    ? React.cloneElement(child, { id, "aria-describedby": error || hint ? msgId : undefined, "aria-invalid": error ? true : child.props["aria-invalid"] })
    : children;
  return (
    <div className={cn("space-y-1.5", className)} role={!linkable && label ? "group" : undefined} aria-labelledby={!linkable && label ? `${auto}-lbl` : undefined}>
      {label && <Label id={`${auto}-lbl`} htmlFor={linkable ? id : undefined}>{label}</Label>}
      {control}
      {error ? <p id={msgId} className="text-sm text-danger-ink">{error}</p> : hint ? <p id={msgId} className="text-[0.82rem] text-muted">{hint}</p> : null}
    </div>
  );
}

/* ---------------- Switch / Checkbox ---------------- */
export function Switch({ className, ...p }: React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      className={cn("peer inline-flex h-7 w-12 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent bg-line-strong transition-colors data-[state=checked]:bg-primary disabled:opacity-50", className)}
      {...p}
    >
      <SwitchPrimitive.Thumb className="pointer-events-none block h-6 w-6 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-5 data-[state=unchecked]:translate-x-0" />
    </SwitchPrimitive.Root>
  );
}

export function Checkbox({ className, ...p }: React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      className={cn("peer h-6 w-6 shrink-0 rounded-md border-2 border-line-strong bg-surface data-[state=checked]:border-primary data-[state=checked]:bg-primary data-[state=checked]:text-white", className)}
      {...p}
    >
      <CheckboxPrimitive.Indicator className="flex items-center justify-center">
        <Check className="h-4 w-4" strokeWidth={3} />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
}

/* ---------------- Progress / Skeleton ---------------- */
export function Progress({ value, className, indicatorClassName }: { value: number; className?: string; indicatorClassName?: string }) {
  return (
    <ProgressPrimitive.Root className={cn("relative h-2 w-full overflow-hidden rounded-full bg-muted-bg", className)} value={value}>
      <ProgressPrimitive.Indicator className={cn("h-full rounded-full bg-primary transition-all duration-500", indicatorClassName)} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </ProgressPrimitive.Root>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-xl bg-muted-bg", className)} />;
}

/* ---------------- Badge ---------------- */
const BADGE = {
  default: "bg-muted-bg text-ink-soft",
  primary: "bg-primary-100 text-primary-800",
  success: "bg-primary-100 text-primary-800",
  warning: "bg-warning-bg text-warning-ink",
  danger: "bg-danger-bg text-danger-ink",
  info: "bg-info-bg text-[#3D5F8F]",
  outline: "border border-line-strong text-ink-soft",
};
export function Badge({ variant = "default", className, ...p }: React.HTMLAttributes<HTMLSpanElement> & { variant?: keyof typeof BADGE }) {
  return <span className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[0.78rem] font-medium [&_svg]:h-3.5 [&_svg]:w-3.5", BADGE[variant], className)} {...p} />;
}

/* ---------------- Tabs ---------------- */
export const Tabs = TabsPrimitive.Root;
export function TabsList({ className, ...p }: React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>) {
  return <TabsPrimitive.List className={cn("inline-flex h-11 items-center gap-1 rounded-xl bg-muted-bg p-1 text-muted overflow-x-auto scrollbar-none max-w-full", className)} {...p} />;
}
export function TabsTrigger({ className, ...p }: React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn("inline-flex h-9 items-center justify-center whitespace-nowrap rounded-lg px-3.5 text-sm font-medium transition-all data-[state=active]:bg-surface data-[state=active]:text-ink data-[state=active]:shadow-card hover:text-ink", className)}
      {...p}
    />
  );
}
export const TabsContent = TabsPrimitive.Content;

/* ---------------- Segmented ---------------- */
export function Segmented<T extends string>({ value, onChange, options, className }: { value: T; onChange: (v: T) => void; options: { value: T; label: React.ReactNode }[]; className?: string }) {
  return (
    <div className={cn("inline-flex rounded-xl bg-muted-bg p-1", className)} role="radiogroup">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn("h-9 rounded-lg px-3.5 text-sm font-medium text-muted transition-all", value === o.value && "bg-surface text-ink shadow-card")}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
