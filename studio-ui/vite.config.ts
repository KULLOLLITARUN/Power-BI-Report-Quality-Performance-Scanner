import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import type { Plugin } from 'vite';

/** Every browser Studio supports reads WOFF2, so drop Fontsource's legacy .woff fallbacks
 * (`, url(x.woff) format('woff')`) before Vite resolves the urls; the .woff files are then
 * never emitted. If a font fails anyway, studio.css's system font stacks take over. */
const woff2Only = (): Plugin => ({
  name: 'pbiscan:woff2-only',
  enforce: 'pre',
  transform(code, id) {
    if (!/\/@fontsource(-variable)?\/.*\.css$/.test(id)) return null;
    return { code: code.replace(/,\s*url\([^)]*\.woff\)\s*format\(['"]woff['"]\)/g, ''), map: null };
  },
});

export default defineConfig({
  root: path.resolve(__dirname),
  plugins: [woff2Only(), react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: process.env.NETLIFY ? 'dist' : '../pbiscan/studio/dist',
    emptyOutDir: true,
    rollupOptions: {
      input: path.resolve(__dirname, 'index.html'),
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom'],
          'vendor-three': ['three'],
          'vendor-anime': ['animejs'],
          'vendor-icons': ['lucide-react'],
        },
      },
    },
  },
});
