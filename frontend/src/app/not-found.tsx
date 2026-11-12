import Link from "next/link";
import { Logo } from "@/components/common";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      <Logo />
      <h1 className="mt-6 text-2xl font-semibold">Page not found</h1>
      <p className="text-muted">The page you were looking for doesn&apos;t exist.</p>
      <Link href="/app" className="inline-flex h-11 items-center rounded-xl bg-primary px-5 font-medium text-white">Go to HealthMate</Link>
    </div>
  );
}
