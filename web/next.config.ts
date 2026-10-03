import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The floating dev badge sits over the bottom-left of every screen. Harmless
  // in development, and exactly the kind of thing that ends up in a demo video.
  devIndicators: false,
};

export default nextConfig;
