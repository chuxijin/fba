import { build } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const directory = dirname(fileURLToPath(import.meta.url))
const targets = [
  { entry: 'popup.html', output: 'assets/[name]-[hash].js', vue: true, public: true },
  { entry: 'background/index.ts', output: 'background.js' },
  { entry: 'content/index.ts', output: 'content.js', vue: true },
  { entry: 'content/interceptor.ts', output: 'injected.js' },
  { entry: 'content/site-auth.ts', output: 'site-auth.js' },
]

async function runBuild() {
  // Popup 初始化 dist；后续脚本保持单文件 IIFE，符合 MV3 content script 的加载方式。
  for (const [index, target] of targets.entries()) {
    console.log(`[Build] ${index + 1}/${targets.length} ${target.entry}`)
    await build({
      root: resolve(directory, 'src'),
      publicDir: target.public ? resolve(directory, 'public') : false,
      plugins: target.vue ? [vue()] : [],
      define: { 'process.env.NODE_ENV': JSON.stringify('production') },
      build: {
        outDir: resolve(directory, 'dist'),
        emptyOutDir: !!target.public,
        rollupOptions: {
          input: resolve(directory, 'src', target.entry),
          output: {
            entryFileNames: target.output,
            ...(!target.public && { format: 'iife', inlineDynamicImports: true }),
          },
        },
      },
    })
  }
  console.log('[Build] 扩展构建完成')
}

runBuild().catch((error) => {
  console.error('[Build] 构建失败:', error)
  process.exitCode = 1
})
