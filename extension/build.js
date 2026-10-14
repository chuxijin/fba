import { build } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))

async function runBuild() {
  console.log('🚀 [Build] 开始多目标隔离构建...')

  // 1. 构建 Popup 主界面应用 (带 public 静态资源复制与 dist 目录初始化)
  console.log('📦 1/4 构建 Popup 弹窗应用...')
  await build({
    root: resolve(__dirname, 'src'),
    publicDir: resolve(__dirname, 'public'),
    plugins: [vue()],
    define: {
      'process.env.NODE_ENV': JSON.stringify('production'),
    },
    build: {
      outDir: resolve(__dirname, 'dist'),
      emptyOutDir: true,
      rollupOptions: {
        input: resolve(__dirname, 'src/popup.html'),
        output: {
          entryFileNames: 'assets/[name]-[hash].js',
        },
      },
    },
  })

  // 2. 构建 Background Service Worker (独立单文件，自包含)
  console.log('📦 2/4 构建 Background Service Worker...')
  await build({
    root: resolve(__dirname, 'src'),
    publicDir: false,
    define: {
      'process.env.NODE_ENV': JSON.stringify('production'),
    },
    build: {
      outDir: resolve(__dirname, 'dist'),
      emptyOutDir: false,
      rollupOptions: {
        input: resolve(__dirname, 'src/background/index.ts'),
        output: {
          entryFileNames: 'background.js',
          format: 'iife',
          name: 'GongkaoBackground',
          inlineDynamicImports: true,
        },
      },
    },
  })

  // 3. 构建 Content Script (严格 IIFE，禁止外部 import，所有依赖强制内联)
  console.log('📦 3/4 构建 Content Script (IIFE 强制内联)...')
  await build({
    root: resolve(__dirname, 'src'),
    publicDir: false,
    plugins: [vue()],
    define: {
      'process.env.NODE_ENV': JSON.stringify('production'),
    },
    build: {
      outDir: resolve(__dirname, 'dist'),
      emptyOutDir: false,
      rollupOptions: {
        input: resolve(__dirname, 'src/content/index.ts'),
        output: {
          entryFileNames: 'content.js',
          format: 'iife',
          name: 'GongkaoContentScript',
          inlineDynamicImports: true,
        },
      },
    },
  })

  // 4. 构建 Main World 注入拦截器 (严格 IIFE，纯净无依赖)
  console.log('📦 4/4 构建 Injected Interceptor (IIFE)...')
  await build({
    root: resolve(__dirname, 'src'),
    publicDir: false,
    define: {
      'process.env.NODE_ENV': JSON.stringify('production'),
    },
    build: {
      outDir: resolve(__dirname, 'dist'),
      emptyOutDir: false,
      rollupOptions: {
        input: resolve(__dirname, 'src/content/interceptor.ts'),
        output: {
          entryFileNames: 'injected.js',
          format: 'iife',
          name: 'GongkaoInterceptor',
          inlineDynamicImports: true,
        },
      },
    },
  })

  console.log('✅ [Build] 扩展全部组件构建完成，所有脚本均符合 Chrome MV3 规范！')
}

runBuild().catch((err) => {
  console.error('❌ 构建失败:', err)
  process.exit(1)
})
