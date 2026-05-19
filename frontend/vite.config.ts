import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  build: {
    lib: {
      entry: resolve(__dirname, 'src/main.ts'),
      name: 'GrowthChat',
      formats: ['iife'],
      fileName: () => 'growth_chat.js',
    },
    outDir: 'dist',
    emptyOutDir: true,
  },
});
