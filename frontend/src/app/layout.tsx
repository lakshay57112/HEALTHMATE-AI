import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { Toaster } from "sonner";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "HealthMate AI — Your Health. Your Family. One Intelligent Companion.", template: "%s · HealthMate AI" },
  description: "Upload once, understand everything. HealthMate AI explains medical reports, turns prescriptions into reminders, and keeps your family in the loop.",
  icons: { icon: "/icon.svg" },
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = { themeColor: "#FAFBFA", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="min-h-screen font-sans">
        <Providers>{children}</Providers>
        <Toaster position="top-center" richColors closeButton toastOptions={{ style: { borderRadius: 14, fontSize: "0.95rem" } }} />
      </body>
    </html>
  );
}
