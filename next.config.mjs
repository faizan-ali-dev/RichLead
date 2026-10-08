/** @type {import('next').NextConfig} */
const nextConfig = {
  // Use a single worker thread for static page analysis. This avoids child
  // process spawning in restricted Windows build environments.
  experimental: {
    cpus: 1,
    workerThreads: true,
  },
  // API calls are handled by app/api/[...path]/route.js so the proxy can pass
  // the original HTTPS scheme to Django instead of letting Django redirect an
  // internal HTTP hop and turning browser POSTs into GETs.
};

export default nextConfig;
