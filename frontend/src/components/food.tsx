"use client";
import Link from "next/link";
import { useState } from "react";
import { Clock, Flame, Leaf } from "lucide-react";
import { Badge } from "@/components/ui/primitives";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type Kind = "bowl" | "flat" | "pieces" | "drink" | "scatter" | "plate";
const ART: Record<string, [Kind, string, string]> = {
  "vegetable-poha": ["bowl", "#F2CD5C", "#7FB069"], "moong-dal-chilla": ["flat", "#C9D86B", "#E76F51"], "oats-upma": ["bowl", "#E8D9A8", "#E76F51"],
  "idli-sambar": ["pieces", "#F7F3EA", "#D9822B"], "besan-chilla": ["flat", "#F0C35C", "#5B9A68"], "ragi-dosa": ["flat", "#9C6B4E", "#F2E8CF"],
  "egg-bhurji-toast": ["plate", "#F6D55C", "#C8A26B"], "curd-fruit-bowl": ["bowl", "#FBFAF5", "#E85D75"], "sprouts-chaat": ["scatter", "#9BCB6E", "#E63946"],
  "roasted-chana": ["scatter", "#C68B59", "#8C5A3C"], "masala-chaas": ["drink", "#F4F1E8", "#6BA368"], "fruit-bowl": ["scatter", "#F4A261", "#90BE6D"],
  "roasted-makhana": ["scatter", "#FAF3E3", "#E9C46A"], "dal-brown-rice": ["plate", "#F2B134", "#B08968"], "rajma-rice": ["plate", "#9E2A2B", "#F1E6D2"],
  "palak-paneer-roti": ["plate", "#4F7942", "#F7F3E8"], "veg-khichdi": ["bowl", "#E9C46A", "#90BE6D"], "lauki-sabzi-roti": ["plate", "#B5C99A", "#D4A373"],
  "grilled-fish-veg": ["plate", "#E9A37C", "#7FB069"], "chicken-curry-roti": ["plate", "#C0602F", "#D4A373"], "chicken-clear-soup": ["bowl", "#F3E2B3", "#90BE6D"],
  "veg-daliya": ["bowl", "#D9B77E", "#7FB069"], "quinoa-pulao": ["bowl", "#EFE3C8", "#E76F51"], "tofu-bhurji-roti": ["plate", "#F4E3A1", "#6A994E"],
  "curd-rice": ["bowl", "#FBF8F0", "#2A9D8F"], "tomato-carrot-soup": ["bowl", "#E4572E", "#F3A712"], "paneer-tikka-salad": ["pieces", "#F28C28", "#90BE6D"],
  dhokla: ["pieces", "#F6D365", "#2A9D8F"], "egg-white-omelette": ["flat", "#FFF5D6", "#6A994E"], "methi-thepla": ["flat", "#C9B26B", "#6A994E"],
};

/** Illustrated, on-brand food art. Used when no photo URL is configured (or a photo fails to load). */
export function FoodArt({ slug, className }: { slug: string; className?: string }) {
  const [kind, main, accent] = ART[slug] || ["plate", "#E9C46A", "#90BE6D"];
  const seed = slug.length;
  const dots = Array.from({ length: 9 }, (_, i) => ({ x: 100 + Math.cos((i * 2.4 + seed) % 6.28) * (18 + (i * 7) % 26), y: 100 + Math.sin((i * 2.4 + seed) % 6.28) * (14 + (i * 5) % 22), r: 3 + (i % 3) }));
  return (
    <svg viewBox="0 0 200 200" className={cn("h-full w-full", className)} aria-hidden>
      <rect width="200" height="200" fill="#EEF4F0" />
      <circle cx="100" cy="108" r="78" fill="#000" opacity="0.05" />
      {kind === "drink" ? (
        <g>
          <path d="M70 50h60l-8 110a10 10 0 0 1-10 9H88a10 10 0 0 1-10-9Z" fill="#fff" stroke="#DCE5DF" strokeWidth="2" />
          <path d="M74 80h52l-6 78a8 8 0 0 1-8 7H88a8 8 0 0 1-8-7Z" fill={main} />
          {dots.slice(0, 4).map((d, i) => <circle key={i} cx={88 + i * 8} cy={90 + (i % 2) * 6} r="2.5" fill={accent} />)}
        </g>
      ) : (
        <g>
          <circle cx="100" cy="100" r="74" fill="#fff" />
          <circle cx="100" cy="100" r="74" fill="none" stroke="#DCE5DF" strokeWidth="2" />
          <circle cx="100" cy="100" r="58" fill="none" stroke="#EEF2EF" strokeWidth="2" />
          {kind === "bowl" && <><circle cx="100" cy="100" r="54" fill={main} /><ellipse cx="88" cy="88" rx="22" ry="12" fill="#fff" opacity="0.18" /></>}
          {kind === "flat" && <><circle cx="100" cy="100" r="50" fill={main} /><circle cx="100" cy="100" r="50" fill="none" stroke="#000" opacity="0.06" strokeWidth="6" /></>}
          {kind === "plate" && <><path d="M100 100 L100 46 A54 54 0 0 1 154 100 Z" fill={main} /><path d="M100 100 L154 100 A54 54 0 0 1 100 154 Z" fill={accent} opacity="0.9" /><circle cx="78" cy="118" r="26" fill="#F3E6C8" /><circle cx="78" cy="118" r="26" fill="none" stroke="#E4D3AE" strokeWidth="3" /></>}
          {kind === "pieces" && [[78, 84], [122, 84], [100, 122], [72, 126], [128, 124]].map(([x, y], i) => <rect key={i} x={x - 15} y={y - 12} width="30" height="24" rx="9" fill={i % 2 ? main : accent} opacity={i % 2 ? 1 : 0.85} />)}
          {kind === "scatter" && dots.concat(dots.map((d) => ({ x: 200 - d.x, y: d.y + 6, r: d.r + 1 }))).map((d, i) => <circle key={i} cx={d.x} cy={d.y} r={d.r + 3} fill={i % 3 ? main : accent} />)}
          {(kind === "bowl" || kind === "flat") && dots.map((d, i) => <circle key={i} cx={d.x} cy={d.y} r={d.r} fill={i % 2 ? accent : "#fff"} opacity={i % 2 ? 0.9 : 0.55} />)}
          <path d="M150 58c8-10 18-12 24-10-2 8-10 16-24 10Z" fill="#7FB069" />
        </g>
      )}
    </svg>
  );
}

export function FoodImage({ food, className }: { food: { slug: string; image_url?: string | null; name: string }; className?: string }) {
  const [failed, setFailed] = useState(false);
  return (
    <div className={cn("relative overflow-hidden bg-[#EEF4F0]", className)}>
      {food.image_url && !failed ? <img src={food.image_url} alt={food.name} className="h-full w-full object-cover" onError={() => setFailed(true)} loading="lazy" /> : <FoodArt slug={food.slug} />}
    </div>
  );
}

const TAG_LABEL: Record<string, string> = { high_protein: "High protein", diabetes_friendly: "Diabetes-friendly", heart_healthy: "Heart-healthy", low_sodium: "Low sodium", budget_friendly: "Budget", easy_to_cook: "Easy" };

export function FoodCard({ food, compact, meal }: { food: any; compact?: boolean; meal?: string }) {
  const { lang, t } = useI18n();
  return (
    <Link href={`/app/nutrition/foods/${food.id}`} className="group block">
      <div className="card overflow-hidden transition-shadow group-hover:shadow-soft">
        <FoodImage food={food} className={compact ? "aspect-[16/10]" : "aspect-[4/3]"} />
        <div className="p-4">
          {meal && <div className="eyebrow mb-1">{t(meal.charAt(0).toUpperCase() + meal.slice(1))}</div>}
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="font-semibold leading-snug">{lang === "hi" && food.name_hi ? food.name_hi : food.name}</div>
              {lang === "hi" && food.name_hi && <div className="text-[0.78rem] text-muted">{food.name}</div>}
            </div>
            <span className={cn("mt-1 h-3 w-3 shrink-0 rounded-sm border-2", food.diet === "non_vegetarian" ? "border-danger" : food.diet === "eggetarian" ? "border-warning" : "border-primary")} title={food.diet}>
              <span className={cn("m-[2px] block h-1 w-1 rounded-full", food.diet === "non_vegetarian" ? "bg-danger" : food.diet === "eggetarian" ? "bg-warning" : "bg-primary")} />
            </span>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.8rem] text-muted tnum">
            <span className="flex items-center gap-1"><Flame className="h-3.5 w-3.5" />{Math.round(food.calories)} kcal</span>
            <span>P {food.protein_g}g</span><span>C {food.carbs_g}g</span><span>F {food.fat_g}g</span>
            <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" />{food.prep_minutes}m</span>
          </div>
          {!compact && (
            <>
              <div className="mt-2.5 flex flex-wrap gap-1">{food.tags.filter((x: string) => TAG_LABEL[x]).slice(0, 3).map((x: string) => <Badge key={x} variant="primary">{TAG_LABEL[x]}</Badge>)}</div>
              {food.reasons?.[0] && <p className="mt-2.5 flex items-start gap-1.5 text-[0.82rem] text-ink-soft"><Leaf className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />{food.reasons[0]}</p>}
            </>
          )}
        </div>
      </div>
    </Link>
  );
}
