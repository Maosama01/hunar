import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// The API runs on :8000 (`make api`). Both the dev server and `vite preview` proxy /api to it,
// so the app and the API share an origin and the service worker can cache API images.
const API = process.env.HUNAR_API ?? "http://localhost:8000";
const proxy = { "/api": { target: API, changeOrigin: true } };

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: false, // registered in src/main.tsx via virtual:pwa-register
      includeAssets: ["icon.svg", "icon-192.png", "icon-512.png", "apple-touch-icon.png"],
      manifest: {
        name: "Hunar: skills and work for electricians, plumbers and carpenters",
        short_name: "Hunar",
        description:
          "Self-check quiz, practical assessment requests and bookings for skilled workers. AI suggests, the assessor decides.",
        lang: "en",
        start_url: "/",
        scope: "/",
        display: "standalone",
        background_color: "#ffffff",
        theme_color: "#0b5d4b",
        icons: [
          { src: "icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
          { src: "icon.svg", sizes: "any", type: "image/svg+xml" },
        ],
      },
      workbox: {
        // Precache the app shell so the app opens offline after the first visit.
        globPatterns: ["**/*.{js,css,html,svg,png,ico,webmanifest}"],
        navigateFallback: "index.html",
        navigateFallbackDenylist: [/^\/api\//],
        cleanupOutdatedCaches: true,
        // autoUpdate: a new build takes over at once (the plugin only sets these itself when it
        // injects the registration script, and we register in src/main.tsx).
        skipWaiting: true,
        clientsClaim: true,
        runtimeCaching: [
          {
            // Evidence images are stored with faces already blurred by the server.
            urlPattern: ({ url }) =>
              url.pathname.startsWith("/api/evidence/") || url.pathname.startsWith("/api/study/items/"),
            handler: "CacheFirst",
            options: {
              cacheName: "hunar-api-images",
              expiration: { maxEntries: 300, maxAgeSeconds: 60 * 60 * 24 * 30 },
              cacheableResponse: { statuses: [200] },
            },
          },
          {
            // Noto Sans Ol Chiki / Meetei Mayek stylesheets, requested only when Santali or Manipuri is
            // chosen; cached so those scripts still render offline after first use.
            urlPattern: ({ url }) => url.origin === "https://fonts.googleapis.com",
            handler: "StaleWhileRevalidate",
            options: {
              cacheName: "hunar-font-css",
              expiration: { maxEntries: 20, maxAgeSeconds: 60 * 60 * 24 * 365 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            urlPattern: ({ url }) => url.origin === "https://fonts.gstatic.com",
            handler: "CacheFirst",
            options: {
              cacheName: "hunar-font-files",
              expiration: { maxEntries: 30, maxAgeSeconds: 60 * 60 * 24 * 365 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
      devOptions: { enabled: false },
    }),
  ],
  server: { port: 5173, strictPort: true, proxy },
  preview: { port: 4173, strictPort: true, proxy },
});
