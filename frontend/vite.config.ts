import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// 前端开发服务器配置
// 关键点：/api 代理到后端 8000，这样前端代码里写相对路径 /api/xxx 即可，
// 不需要在前端硬编码后端地址，也不需要依赖 CORS。
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
