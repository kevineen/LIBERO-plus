import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Thor 上で LAN からアクセスする想定
  allowedDevOrigins: ["*"],
  experimental: {
    // サーバから experiments/ を読む
  },
};

export default nextConfig;
