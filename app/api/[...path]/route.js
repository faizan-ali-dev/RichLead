import { createDjangoProxy } from "../../lib/django-proxy.js";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
const proxyToDjango = createDjangoProxy("/api", false);

export const GET = proxyToDjango;
export const HEAD = proxyToDjango;
export const POST = proxyToDjango;
export const PUT = proxyToDjango;
export const PATCH = proxyToDjango;
export const DELETE = proxyToDjango;
export const OPTIONS = proxyToDjango;
