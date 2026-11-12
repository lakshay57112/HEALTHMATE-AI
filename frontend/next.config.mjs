/** @type {import('next').NextConfig} */
// /api/* is proxied at runtime by src/app/api/[...path]/route.ts (reads BACKEND_URL per request).
const nextConfig = {
  reactStrictMode: true,
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  compress: false, // keep Server-Sent Events from the assistant unbuffered
  poweredByHeader: false,
  async headers() {
    return [{
      source: "/(.*)",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy", value: "camera=(self), microphone=(self), geolocation=()" },
      ],
    }];
  },
  images: { remotePatterns: [{ protocol: "https", hostname: "upload.wikimedia.org" }, { protocol: "https", hostname: "images.unsplash.com" }] },
};
export default nextConfig;
