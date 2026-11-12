import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import { Logo } from "@/components/common";

export function AuthLayout({ title, subtitle, children, footer }: { title: string; subtitle?: string; children: React.ReactNode; footer?: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_1.1fr]">
      <div className="flex flex-col px-6 py-8 sm:px-12">
        <Link href="/"><Logo /></Link>
        <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-10">
          <h1 className="text-[1.9rem] font-semibold tracking-tight">{title}</h1>
          {subtitle && <p className="mt-2 text-muted">{subtitle}</p>}
          <div className="mt-8">{children}</div>
          {footer && <div className="mt-6 text-sm text-muted">{footer}</div>}
        </div>
      </div>
      <div className="hidden flex-col justify-between bg-secondary p-12 lg:flex">
        <div />
        <div className="max-w-md">
          <p className="text-[1.6rem] font-medium leading-snug text-primary-800">“My father finally understands his own reports — and I get a message if he forgets his afternoon tablet.”</p>
          <p className="mt-4 text-primary-800/70">The kind of calm we built HealthMate for.</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-primary-800/80"><ShieldCheck className="h-4 w-4" /> Encrypted documents · consent-based sharing · no AI diagnoses</div>
      </div>
    </div>
  );
}
