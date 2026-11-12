/**
 * Runtime proxy: forwards /api/* to the FastAPI backend.
 * BACKEND_URL is read on every request (not baked in at build time), so the same build works locally,
 * in Docker Compose and on hosts like Render. Streams request and response bodies (uploads, SSE).
 */
import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const HOP_BY_HOP = new Set(["connection", "keep-alive", "transfer-encoding", "upgrade", "proxy-connection", "te", "trailer", "host", "content-length", "content-encoding"]);

function backend() {
  return (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
}

async function proxy(req: NextRequest, { params }: { params: { path: string[] } }) {
  const target = `${backend()}/api/${params.path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key)) headers.set(key, value);
  });
  const fwd = req.headers.get("x-forwarded-for") || req.ip;
  if (fwd) headers.set("x-forwarded-for", fwd);
  headers.set("x-forwarded-proto", req.nextUrl.protocol.replace(":", ""));

  const init: RequestInit & { duplex?: "half" } = { method: req.method, headers, redirect: "manual", cache: "no-store" };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = req.body;
    init.duplex = "half";
  }
  let res: Response;
  try {
    res = await fetch(target, init);
  } catch {
    return Response.json({ detail: "The HealthMate service is starting up or unreachable. Please try again in a moment." }, { status: 502 });
  }
  const out = new Headers();
  res.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key) && key !== "set-cookie") out.set(key, value);
  });
  const cookies = (res.headers as Headers & { getSetCookie?: () => string[] }).getSetCookie?.() ?? [];
  for (const c of cookies) out.append("set-cookie", c);
  return new Response(res.body, { status: res.status, statusText: res.statusText, headers: out });
}

export { proxy as DELETE, proxy as GET, proxy as HEAD, proxy as PATCH, proxy as POST, proxy as PUT };
