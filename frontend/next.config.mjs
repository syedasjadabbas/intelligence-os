/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  // Allowed development origins for HMR and proxy WebSockets
  allowedDevOrigins: [
    "localhost:3000",
    "127.0.0.1:3000",
    "localhost",
    "127.0.0.1",
  ],
  turbopack: {},
  webpack: (config, { dev, isServer }) => {
    if (dev && !isServer) {
      // Preserve stable watch options for hot module reloading across dev proxies
      config.watchOptions = {
        poll: 1000,
        aggregateTimeout: 300,
      };
    }
    return config;
  },
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: "http://127.0.0.1:8000/api/v1/:path*",
      },
    ];
  },
};

export default nextConfig;
