import type { NextConfig } from "next";

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

const nextConfig: NextConfig = {
  /* config options here */
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${API_URL}/:path*`, // 代理到FastAPI后端
        basePath: false,
      },
    ];
  },
  async redirects() {
    return [
      {
        source: '/',
        destination: '/aipotluck',
        basePath: false,
        permanent: false,
      },
    ];
  },
  devIndicators:false,
  basePath: '/aipotluck',
};

export default nextConfig;
