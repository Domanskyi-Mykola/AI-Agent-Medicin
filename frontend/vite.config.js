import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Проксі, щоб фронтенд ходив на /api без CORS-налаштувань
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
