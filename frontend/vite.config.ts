import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig(({ command }) => ({
  plugins: [react()],
  define: command === 'build' ? {
    'process.env.NODE_ENV': JSON.stringify('production'),
  } : {},
  build: {
    lib: {
      entry: resolve(__dirname, 'src/main.ts'),
      name: 'GrowthChat',
      formats: ['iife'],
      fileName: () => 'chat.js',
    },
    outDir: 'dist',
    emptyOutDir: true,
  },
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
  },
}));
