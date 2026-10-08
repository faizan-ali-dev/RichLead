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

export function createDjangoProxy(publicPrefix, stripPublicPrefix = true) {
  return async function proxyToDjango(request) {
    const incomingUrl = new URL(request.url);
    const requestedPath = stripPublicPrefix
      ? incomingUrl.pathname.slice(publicPrefix.length) || "/"
      : incomingUrl.pathname;
    const backendPath = requestedPath.endsWith("/") ? requestedPath : `${requestedPath}/`;

    // The bridge is limited to the API and the service health endpoint.
    if (!backendPath.startsWith("/api/") && backendPath !== "/healthz/") {
      return Response.json({ detail: "Not found." }, { status: 404 });
    }

    const upstreamUrl = new URL(`${backendPath}${incomingUrl.search}`, backendBaseUrl);
    const headers = new Headers(request.headers);
    for (const name of hopByHopHeaders) headers.delete(name);

    // Django enables SECURE_SSL_REDIRECT in production. Preserve the public
    // request's HTTPS context across the internal HTTP connection.
    const publicHost = request.headers.get("x-forwarded-host") || request.headers.get("host");
    headers.set("x-forwarded-host", publicHost || incomingUrl.host);
    const publicProtocol = process.env.NODE_ENV === "production"
      ? "https"
      : incomingUrl.protocol.slice(0, -1);
    headers.set("x-forwarded-proto", publicProtocol);

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
  };
}
