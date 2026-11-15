import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  server: {
    // Forward /api calls to the Python backend
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
});
