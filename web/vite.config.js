import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Port 5190 so it never collides with the other projects' dev servers
// (grounded-rag runs on 5180). The proxy means the browser only ever talks to
// one origin, so there is no CORS to debug at 17:00 on a Friday.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5190,
    proxy: { "/api": "http://localhost:8010" },
  },
});
