import type { NextConfig } from 'next';

// Browser only calls same-origin /api/... . Next.js proxies to Python FastAPI.
const backend = process.env.BACKEND_INTERNAL_URL || 'http://127.0.0.1:8000';
const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${backend}/api/:path*` }];
  },
};
export default nextConfig;
