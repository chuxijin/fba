import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  define: {
    'process.env.NODE_ENV': JSON.stringify(process.env.NODE_ENV || 'production'),
  },
  root: resolve(__dirname, 'src'),
  publicDir: resolve(__dirname, 'public'),
  build: {
    outDir: resolve(__dirname, 'dist'),
    emptyOutDir: true,
    sourcemap: process.env.NODE_ENV === 'development',
    rollupOptions: {
      input: {
        popup: resolve(__dirname, 'src/popup.html'),
        background: resolve(__dirname, 'src/background/index.ts'),
        content: resolve(__dirname, 'src/content/index.ts'),
        injected: resolve(__dirname, 'src/content/interceptor.ts'),
      },
      output: {
        entryFileNames: (chunkInfo) => {
          if (['background', 'content', 'injected'].includes(chunkInfo.name)) {
            return '[name].js'
          }
          return 'assets/[name]-[hash].js'
        },
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: (assetInfo) => {
          if (assetInfo.name && assetInfo.name.endsWith('.css')) {
            if (assetInfo.name.includes('content')) {
              return 'content.css'
            }
          }
          return 'assets/[name]-[hash].[ext]'
        },
      },
    },
  },
})
