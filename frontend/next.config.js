/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Disable caching to save disk space
  webpack: (config) => {
    config.cache = false;
    return config;
  },
}

module.exports = nextConfig
