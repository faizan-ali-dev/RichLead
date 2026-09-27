/** @type {import('next').NextConfig} */
const nextConfig = {
  // Keep browser requests same-origin in production; Django listens on loopback
  // behind Nginx. In development Next proxies the API to runserver.
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${process.env.DJANGO_INTERNAL_URL || "http://127.0.0.1:8000"}/api/:path*` },
    ];
  },
};

export default nextConfig;
