import { readFile } from 'node:fs/promises'
import ts from 'typescript'

const modules = new Map()
export function compileSource(source, module = ts.ModuleKind.CommonJS) {
  return ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ESNext, module } }).outputText
}

/** 加载真实 TS 依赖图，各测试不再维护一套易漏依赖的字符串替换。 */
export function typeScriptModuleUrl(file) {
  const path = new URL(file).href
  if (!modules.has(path)) modules.set(path, (async () => {
    let code = compileSource(await readFile(new URL(path), 'utf8'), ts.ModuleKind.ESNext)
    const imports = [...code.matchAll(/(?:from\s+|import\s+)(['"])(\.{1,2}\/[^'"]+)\1/g)]
    for (const match of imports) {
      const dependency = new URL(match[2].endsWith('.ts') ? match[2] : `${match[2]}.ts`, path)
      const url = await typeScriptModuleUrl(dependency)
      code = code.replace(match[0], match[0].replace(`${match[1]}${match[2]}${match[1]}`, JSON.stringify(url)))
    }
    return `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`
  })())
  return modules.get(path)
}

export async function importTypeScript(file) { return import(await typeScriptModuleUrl(file)) }
