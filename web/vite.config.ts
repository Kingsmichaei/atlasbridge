import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// In development the gateway runs on :8000. Proxying keeps everything same-origin,
// so the session cookie works without any CORS changes. The Host header is left as
// localhost:5173 (no changeOrigin) so the gateway's Origin check matches.
const gateway = "http://localhost:8000";
const proxied = ["/v1", "/auth", "/account", "/admin", "/health", "/static", "/favicon.ico", "/classic", "/openapi.json"];

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(proxied.map((p) => [p, { target: gateway }])),
  },
});
