import { readFile } from 'node:fs/promises'
import ts from 'typescript'

const modules = new Map()
export function compileSource(source, module = ts.ModuleKind.CommonJS) {
  return ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ESNext, module } }).outputText
}

/**
 * 加载真实 TS 依赖图，各测试不再维护一套易漏依赖的字符串替换。
 * define 模拟构建期注入的全局常量（如 __API_BASE__ / __IS_PROD__），
 * 让同一份源码可以在开发与生产两种构建参数下被隔离加载。
 */
export function typeScriptModuleUrl(file, define) {
  const path = new URL(file).href
  const key = `${path}::${define ? JSON.stringify(define) : ''}`
  if (!modules.has(key)) modules.set(key, (async () => {
    let code = compileSource(await readFile(new URL(path), 'utf8'), ts.ModuleKind.ESNext)
    if (define) {
      code = Object.entries(define).map(([name, value]) => `const ${name} = ${JSON.stringify(value)};`).join('') + code
    }
    const imports = [...code.matchAll(/(?:from\s+|import\s+)(['"])(\.{1,2}\/[^'"]+)\1/g)]
    for (const match of imports) {
      const dependency = new URL(match[2].endsWith('.ts') ? match[2] : `${match[2]}.ts`, path)
      const url = await typeScriptModuleUrl(dependency, define)
      code = code.replace(match[0], match[0].replace(`${match[1]}${match[2]}${match[1]}`, JSON.stringify(url)))
    }
    return `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`
  })())
  return modules.get(key)
}

export async function importTypeScript(file, define) { return import(await typeScriptModuleUrl(file, define)) }
