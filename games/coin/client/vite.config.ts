import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// base: "./" -> relative asset URLs, so the built bundle works when served from
// /game-client/{slug}@{n}/ (prod) or /client/ (harness) and inside the
// opaque-origin sandboxed iframe. Default outDir is "dist" (-> client/dist).
export default defineConfig({
  plugins: [vue()],
  base: "./",
});
