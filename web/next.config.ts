import type { NextConfig } from "next";

/** Where FastAPI runs. On the laptop, the default; deployed, an env var. */
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // The floating dev badge sits over the bottom-left of every screen. Harmless
  // in development, and exactly the kind of thing that ends up in a demo video.
  devIndicators: false,

  // A real phone on the same wifi opens the laptop by its network address, and
  // Next 16 blocks its dev scripts for any host but localhost, so the page never
  // hydrates. Private ranges only (home wifi, office, a phone's hotspot); the
  // deployed build does not use this.
  allowedDevOrigins: ["192.168.*.*", "10.*.*.*", "172.20.10.*"],

  // The browser only ever talks to /api on this origin. A judge's phone needs
  // one URL, and there is no CORS configuration to get wrong on the day.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;
