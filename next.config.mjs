/** @type {import('next').NextConfig} */
const djangoInternalUrl = (
  process.env.DJANGO_INTERNAL_URL ||
  (process.env.NODE_ENV === "production" ? "http://127.0.0.1:8011" : "http://127.0.0.1:8000")
).replace(/\/+$/, "");

const nextConfig = {
  // Use a single worker thread for static page analysis. This avoids child
  // process spawning in restricted Windows build environments.
  experimental: {
    cpus: 1,
    workerThreads: true,
  },
  // Keep browser requests same-origin in production; Django listens on loopback
  // behind Nginx. In development Next proxies the API to runserver.
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${djangoInternalUrl}/api/:path*` },
    ];
  },
};

export default nextConfig;
