"use client";
export default function GlobalError({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 px-6 text-center">
      <h1 className="text-xl font-semibold">Something went wrong</h1>
      <p className="max-w-md text-sm text-muted">{error.message || "Please try again."}</p>
      <button onClick={reset} className="mt-2 h-11 rounded-xl bg-primary px-5 font-medium text-white">Try again</button>
    </div>
  );
}
