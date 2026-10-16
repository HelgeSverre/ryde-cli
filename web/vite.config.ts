import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: './',
  // Never copy public/data into a distributable, even if a developer has
  // private data in their checkout. Data is served by the Python CLI at runtime.
  publicDir: false,
  build: {target: 'es2022', sourcemap: false, outDir: '../src/ryde_cli/web', emptyOutDir: true},
});
