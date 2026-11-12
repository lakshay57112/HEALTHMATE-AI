/** @type {import('next').NextConfig} */
const backend = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const nextConfig = {
  reactStrictMode: true,
  compress: false, // keep Server-Sent Events from the assistant unbuffered
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
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
