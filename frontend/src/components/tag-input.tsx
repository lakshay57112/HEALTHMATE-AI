"use client";
import { useState } from "react";
import { X } from "lucide-react";
import { Badge, Input } from "@/components/ui/primitives";

export function TagInput({ value, onChange, placeholder, suggestions = [] }: { value: string[]; onChange: (v: string[]) => void; placeholder?: string; suggestions?: string[] }) {
  const [text, setText] = useState("");
  const add = (t: string) => { const v = t.trim(); if (v && !value.includes(v)) onChange([...value, v]); setText(""); };
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">{value.map((v) => <Badge key={v} variant="primary" className="py-1 text-sm">{v}<button onClick={() => onChange(value.filter((x) => x !== v))} aria-label={`Remove ${v}`}><X className="h-3.5 w-3.5" /></button></Badge>)}</div>
      <Input value={text} placeholder={placeholder} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); add(text); } }} onBlur={() => text && add(text)} />
      {suggestions.length > 0 && <div className="flex flex-wrap gap-1.5">{suggestions.filter((s) => !value.includes(s)).map((s) => <button key={s} type="button" onClick={() => add(s)} className="rounded-lg border border-dashed border-line-strong px-2.5 py-1 text-[0.8rem] text-muted hover:border-primary hover:text-primary">+ {s}</button>)}</div>}
    </div>
  );
}

