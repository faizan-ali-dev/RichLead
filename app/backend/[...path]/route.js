const backendBaseUrl = (
  process.env.DJANGO_INTERNAL_URL ||
  (process.env.NODE_ENV === "production" ? "http://127.0.0.1:8011" : "http://127.0.0.1:8000")
).replace(/\/+$/, "");

const hopByHopHeaders = [
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
];

async function proxyToDjango(request) {
  const incomingUrl = new URL(request.url);
  const requestedPath = incomingUrl.pathname.slice("/backend".length) || "/";
  const backendPath = requestedPath.endsWith("/") ? requestedPath : `${requestedPath}/`;

  // This endpoint is only a same-origin bridge to Django's API and health check.
  if (!backendPath.startsWith("/api/") && backendPath !== "/healthz/") {
    return Response.json({ detail: "Not found." }, { status: 404 });
  }

  const upstreamUrl = new URL(`${backendPath}${incomingUrl.search}`, backendBaseUrl);
  const headers = new Headers(request.headers);
  for (const name of hopByHopHeaders) headers.delete(name);

  // Django enables SECURE_SSL_REDIRECT in production. Tell it the original
  // browser connection was HTTPS so POST requests are not redirected to GET.
  const publicHost = request.headers.get("host");
  headers.set("x-forwarded-host", publicHost || incomingUrl.host);
  headers.set("x-forwarded-proto", "https");

  const hasBody = request.method !== "GET" && request.method !== "HEAD";

  try {
    const upstream = await fetch(upstreamUrl, {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      ...(hasBody ? { duplex: "half" } : {}),
      redirect: "manual",
      cache: "no-store",
      signal: request.signal,
    });

    const responseHeaders = new Headers(upstream.headers);
    for (const name of hopByHopHeaders) responseHeaders.delete(name);
    responseHeaders.delete("content-encoding");
    responseHeaders.delete("content-length");

    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  } catch {
    return Response.json({ detail: "RichLead API is temporarily unavailable." }, { status: 502 });
  }
}

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const GET = proxyToDjango;
export const HEAD = proxyToDjango;
export const POST = proxyToDjango;
export const PUT = proxyToDjango;
export const PATCH = proxyToDjango;
export const DELETE = proxyToDjango;
export const OPTIONS = proxyToDjango;
