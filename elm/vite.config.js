import { defineConfig } from "vite";
import elmPlugin from "vite-plugin-elm";

export default defineConfig({
  root: "static",
  plugins: [
    elmPlugin({
      debug: process.env.NODE_ENV !== "production",
      optimize: process.env.NODE_ENV === "production",
    }),
  ],
  server: {
    port: 3000,
    open: true,
  },
  build: {
    outDir: "../dist",
    emptyOutDir: true,
  },
  resolve: {
    alias: {
      "@js": "/js",
    },
  },
});
