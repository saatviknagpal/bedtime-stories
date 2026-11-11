import type { NextConfig } from "next";

// Static export: FastAPI serves web/out, so the site and API share one origin.
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
};

export default nextConfig;
