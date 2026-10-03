import type { NextConfig } from "next";

/** Where FastAPI runs. On the laptop, the default; deployed, an env var. */
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // The floating dev badge sits over the bottom-left of every screen. Harmless
  // in development, and exactly the kind of thing that ends up in a demo video.
  devIndicators: false,

  // The browser only ever talks to /api on this origin. A judge's phone needs
  // one URL, and there is no CORS configuration to get wrong on the day.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;
