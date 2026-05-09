#!/usr/bin/env node
// 从运行中的 fba 后端拉取 OpenAPI schema, 写到 packages/api-sdk/openapi.json
//
// 为什么不用静态 import (旧方案): backend.app.router 只包含 app 路由,
// plugin 路由要 build_final_router() 在 app 启动时才会注入。
// 直接调用运行中的 /openapi 端点是唯一保证 schema 完整的办法。
//
// 用法:
//   node scripts/run-dump-openapi.mjs                 # 默认 http://127.0.0.1:8000/openapi
//   FBA_OPENAPI_URL=http://localhost:8000/openapi ... # 自定义地址
import { writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const outputPath = resolve(__dirname, '..', 'openapi.json');

const url = process.env.FBA_OPENAPI_URL || 'http://127.0.0.1:8000/openapi';

console.log(`[dump_openapi] fetching ${url}`);

try {
  const res = await fetch(url, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    console.error(`[dump_openapi] HTTP ${res.status} ${res.statusText}`);
    process.exit(1);
  }
  const schema = await res.json();
  const paths = schema.paths || {};
  const opCount = Object.values(paths).reduce(
    (n, methods) =>
      n + Object.keys(methods).filter(m => ['get', 'post', 'put', 'delete', 'patch'].includes(m.toLowerCase())).length,
    0,
  );
  const schemaCount = Object.keys(schema.components?.schemas || {}).length;

  writeFileSync(outputPath, JSON.stringify(schema, null, 2), 'utf-8');

  console.log(`[OK] OpenAPI schema written: ${outputPath}`);
  console.log(`     paths      : ${Object.keys(paths).length}`);
  console.log(`     operations : ${opCount}`);
  console.log(`     schemas    : ${schemaCount}`);
} catch (err) {
  console.error(`[dump_openapi] fetch failed: ${err.message}`);
  console.error('  请确认 fba 后端已启动 (默认 http://127.0.0.1:8000)。');
  console.error('  自定义地址: 设置 FBA_OPENAPI_URL 环境变量。');
  process.exit(1);
}
