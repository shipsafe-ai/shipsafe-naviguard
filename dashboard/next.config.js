/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  env: {
    NAVIGUARD_API_URL: process.env.NAVIGUARD_API_URL || 'http://localhost:8080',
  },
}

module.exports = nextConfig
