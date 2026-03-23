/**
 * OpenAPI 类型自动生成脚本
 *
 * 用法：
 *   pnpm generate                          # 使用默认地址
 *   OPENAPI_URL=https://api.example.com/openapi.json pnpm generate
 *
 * 生成产物：src/types/__generated__.ts
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUTPUT_FILE = path.resolve(__dirname, '../src/types/__generated__.ts');
const DEFAULT_URL = 'http://127.0.0.1:8000/openapi';

async function main() {
  const url = process.env['OPENAPI_URL'] || DEFAULT_URL;
  console.log(`\n📡 Fetching OpenAPI schema from: ${url}\n`);

  // 动态导入 openapi-typescript
  const { default: openapiTS, astToString } = await import('openapi-typescript');

  const source = new URL(url);
  const ast = await openapiTS(source, {
    exportType: true,
    alphabetize: true,
  });
  
  const output = astToString(ast);

  // 写入文件
  const header = [
    '/* eslint-disable */',
    '/* tslint:disable */',
    '/**',
    ' * 由 OpenAPI 自动生成 — 请勿手动修改',
    ` * 数据源: ${url}`,
    ` * 生成时间: ${new Date().toISOString()}`,
    ' */',
    '',
  ].join('\n');

  fs.writeFileSync(OUTPUT_FILE, header + output, 'utf-8');
  console.log(`✅ Types generated → ${path.relative(process.cwd(), OUTPUT_FILE)}`);
  console.log(`   (${(fs.statSync(OUTPUT_FILE).size / 1024).toFixed(1)} KB)\n`);
}

main().catch((err) => {
  console.error('❌ Failed to generate types:', err.message || err);
  process.exit(1);
});
