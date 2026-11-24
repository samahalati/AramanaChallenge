import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const proxy = { "/api": "http://127.0.0.1:8000" };   // Django API; in production Django serves the built app itself
export default defineConfig({ plugins: [react()], server: { port: 5173, proxy }, preview: { port: 5173, proxy, allowedHosts: true } });
