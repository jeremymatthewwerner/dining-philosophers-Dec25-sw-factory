import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable standalone output for Docker deployment
  output: "standalone",
  // Allow Wikipedia images for thinker avatars
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "upload.wikimedia.org",
        pathname: "/wikipedia/**",
      },
    ],
  },
  // Add build-time environment variable for version tracking
  env: {
    NEXT_PUBLIC_BUILD_TIME: new Date().toISOString(),
  },
  // Enable generateBuildId for cache busting (this is default but making it explicit)
  generateBuildId: async () => {
    // Use timestamp + random string for unique build IDs
    return `${Date.now()}-${Math.random().toString(36).substring(7)}`;
  },
};

export default nextConfig;
