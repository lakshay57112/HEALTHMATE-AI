"use client";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fmtDate } from "@/lib/utils";

const C = { primary: "#4D8B73", soft: "#A9CBB8", grid: "#EEF1EF", muted: "#84918A", warning: "#E9AA53", danger: "#D96C6C", info: "#6C8EBF" };

function TooltipBox({ active, payload, label, unit }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-line bg-surface px-3 py-2 text-xs shadow-soft">
      <div className="mb-1 text-muted">{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2 font-medium tnum">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color }} />
          {p.name}: {p.value} {unit}
        </div>
      ))}
    </div>
  );
}

export function Sparkline({ data, dataKey = "value", color = C.primary, height = 44 }: { data: any[]; dataKey?: string; color?: string; height?: number }) {
  if (!data?.length) return <div style={{ height }} />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={`sg-${color}`} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.18} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} fill={`url(#sg-${color})`} dot={false} isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function MeasurementChart({ items, kind, height = 240 }: { items: any[]; kind: string; height?: number }) {
  const data = items.map((m) => ({ date: fmtDate(m.measured_at, { day: "numeric", month: "short" }), value: m.value, value2: m.value2 }));
  const unit = items[0]?.unit || "";
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 10, right: 8, bottom: 0, left: -18 }}>
        <CartesianGrid stroke={C.grid} vertical={false} />
        <XAxis dataKey="date" tick={{ fontSize: 12, fill: C.muted }} tickLine={false} axisLine={false} minTickGap={20} />
        <YAxis tick={{ fontSize: 12, fill: C.muted }} tickLine={false} axisLine={false} domain={["dataMin - 8", "dataMax + 8"]} />
        <Tooltip content={<TooltipBox unit={unit} />} />
        <Line type="monotone" dataKey="value" name={kind === "blood_pressure" ? "Systolic" : "Value"} stroke={C.primary} strokeWidth={2.5} dot={{ r: 3, fill: C.primary }} activeDot={{ r: 5 }} />
        {kind === "blood_pressure" && <Line type="monotone" dataKey="value2" name="Diastolic" stroke={C.info} strokeWidth={2.5} dot={{ r: 3, fill: C.info }} />}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function ParameterTrend({ history, height = 200 }: { history: any[]; height?: number }) {
  const pts = history.filter((h) => h.value != null);
  const data = pts.map((h) => ({ date: fmtDate(h.date, { day: "numeric", month: "short", year: "numeric" }), value: h.value }));
  const lo = pts.at(-1)?.ref_low;
  const hi = pts.at(-1)?.ref_high;
  const vals = pts.map((p) => p.value).concat([lo, hi].filter((x) => x != null) as number[]);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const pad = (max - min) * 0.25 || 1;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 10, right: 12, bottom: 0, left: -12 }}>
        <CartesianGrid stroke={C.grid} vertical={false} />
        {(lo != null || hi != null) && <ReferenceArea y1={lo ?? min - pad} y2={hi ?? max + pad} fill={C.primary} fillOpacity={0.07} ifOverflow="extendDomain" />}
        <XAxis dataKey="date" tick={{ fontSize: 12, fill: C.muted }} tickLine={false} axisLine={false} />
        <YAxis tick={{ fontSize: 12, fill: C.muted }} tickLine={false} axisLine={false} domain={[Math.floor(min - pad), Math.ceil(max + pad)]} />
        <Tooltip content={<TooltipBox unit={pts[0]?.unit || ""} />} />
        <Line type="monotone" dataKey="value" name="Result" stroke={C.primary} strokeWidth={2.5} dot={{ r: 4, fill: "#fff", stroke: C.primary, strokeWidth: 2 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function AdherenceBars({ daily, height = 120 }: { daily: { date: string; percent: number | null; taken: number; expected: number }[]; height?: number }) {
  const data = daily.map((d) => ({ day: new Date(d.date + "T00:00:00").toLocaleDateString("en-IN", { weekday: "short" }), percent: d.percent ?? 0, label: d.expected ? `${d.taken}/${d.expected}` : "—" }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
        <XAxis dataKey="day" tick={{ fontSize: 11, fill: C.muted }} tickLine={false} axisLine={false} />
        <YAxis domain={[0, 100]} hide />
        <Tooltip cursor={{ fill: "#F3F5F3" }} content={({ active, payload }: any) => active && payload?.length ? <div className="rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs shadow-soft tnum">{payload[0].payload.label} doses · {payload[0].value}%</div> : null} />
        <Bar dataKey="percent" radius={[6, 6, 6, 6]} fill={C.primary} maxBarSize={22} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function Ring({ value, size = 104, stroke = 10, label }: { value: number | null; size?: number; stroke?: number; label?: string }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const v = value ?? 0;
  const color = value == null ? C.grid : v >= 80 ? C.primary : v >= 60 ? C.warning : C.danger;
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={C.grid} strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - v / 100)} style={{ transition: "stroke-dashoffset .8s ease" }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-semibold tnum">{value == null ? "—" : `${value}%`}</span>
        {label && <span className="text-[0.7rem] text-muted">{label}</span>}
      </div>
    </div>
  );
}
