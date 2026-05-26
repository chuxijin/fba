import { setupSdk } from '../src/runtime/axios';

type Scenario = {
  name: string;
  respond: (callIndex: number) => { status: number; body: any };
  refresh: () => Promise<boolean>;
  expected: {
    refreshCalled: number;
    unauthorizedCalled: number;
    finalResult: 'success' | 'reject';
  };
};

const scenarios: Scenario[] = [
  {
    name: '1. JWT 自然过期: refresh 成功, 自动重放原请求',
    respond: (i) =>
      i === 0
        ? { status: 401, body: { code: 401, msg: 'Token 已过期', data: null } }
        : { status: 200, body: { code: 200, msg: 'ok', data: { hello: 'world' } } },
    refresh: async () => true,
    expected: { refreshCalled: 1, unauthorizedCalled: 0, finalResult: 'success' },
  },
  {
    name: '2. 服务端踢人 (Token 已失效): 不 refresh, 直接登出',
    respond: () => ({ status: 401, body: { code: 401, msg: 'Token 已失效', data: null } }),
    refresh: async () => true,
    expected: { refreshCalled: 0, unauthorizedCalled: 1, finalResult: 'reject' },
  },
  {
    name: '3. Token 格式错乱 (Token 无效): 不 refresh, 直接登出',
    respond: () => ({ status: 401, body: { code: 401, msg: 'Token 无效', data: null } }),
    refresh: async () => true,
    expected: { refreshCalled: 0, unauthorizedCalled: 1, finalResult: 'reject' },
  },
  {
    name: '4. JWT 过期 但 refresh 失败 (refresh token 也过期): 尝试一次, fallback 登出',
    respond: () => ({ status: 401, body: { code: 401, msg: 'Token 已过期', data: null } }),
    refresh: async () => false,
    expected: { refreshCalled: 1, unauthorizedCalled: 1, finalResult: 'reject' },
  },
  {
    name: '5. JWT 过期 + refresh 自称成功但重放仍 401: _retry 标记防止无限循环',
    respond: () => ({ status: 401, body: { code: 401, msg: 'Token 已过期', data: null } }),
    refresh: async () => true,
    expected: { refreshCalled: 1, unauthorizedCalled: 1, finalResult: 'reject' },
  },
];

async function runScenario(s: Scenario) {
  let refreshCalled = 0;
  let unauthorizedCalled = 0;
  let callIndex = 0;

  const adapter = (config: any) =>
    new Promise((resolve) => {
      const result = s.respond(callIndex++);
      resolve({
        data: result.body,
        status: result.status,
        statusText: String(result.status),
        headers: {},
        config,
      });
    });

  const instance = await setupSdk({
    baseURL: 'http://fake',
    adapter: adapter as any,
    getToken: () => 'fake-token',
    onTokenExpired: async () => {
      refreshCalled++;
      return s.refresh();
    },
    onUnauthorized: () => {
      unauthorizedCalled++;
    },
  });

  let finalResult: 'success' | 'reject' = 'reject';
  try {
    await instance.get('/api/test');
    finalResult = 'success';
  }
  catch {
    finalResult = 'reject';
  }

  const pass =
    refreshCalled === s.expected.refreshCalled &&
    unauthorizedCalled === s.expected.unauthorizedCalled &&
    finalResult === s.expected.finalResult;

  return {
    name: s.name,
    pass,
    actual: { refreshCalled, unauthorizedCalled, finalResult, callIndex },
    expected: s.expected,
  };
}

async function main() {
  const results = [];
  for (const s of scenarios) {
    const r = await runScenario(s);
    results.push(r);
  }

  // 额外的多实例 / 并发 / hooks / retry 测试 (使用 createSdk 避免模块级状态污染)
  const extras = await runExtraScenarios();
  results.push(...extras);

  console.log('\n=== Token Refresh Test Results ===\n');
  for (const r of results) {
    const icon = r.pass ? 'PASS' : 'FAIL';
    console.log(`[${icon}] ${r.name}`);
    if (!r.pass) {
      console.log(`       expected: ${JSON.stringify(r.expected)}`);
      console.log(`       actual:   ${JSON.stringify(r.actual)}`);
    }
  }

  const passCount = results.filter((r) => r.pass).length;
  const total = results.length;
  console.log(`\nTotal: ${passCount}/${total} passed\n`);
  process.exit(passCount === total ? 0 : 1);
}

interface ExtraResult {
  name: string;
  pass: boolean;
  expected?: unknown;
  actual?: unknown;
}

async function runExtraScenarios(): Promise<ExtraResult[]> {
  const { createSdk } = await import('../src/runtime/axios');
  const out: ExtraResult[] = [];

  // ---- A. 并发 refresh dedupe: 5 个请求同时 401, 只触发一次 refresh ----
  {
    let refreshCalled = 0;
    let callIndex = 0;
    const sdk = createSdk({
      baseURL: 'http://fake',
      adapter: ((config: any) =>
        new Promise((resolve) => {
          const i = callIndex++;
          // 前 5 次返回 Token 已过期, 之后所有都成功
          const result =
            i < 5
              ? { status: 401, body: { code: 401, msg: 'Token 已过期', data: null } }
              : { status: 200, body: { code: 200, msg: 'ok', data: { i } } };
          resolve({
            data: result.body,
            status: result.status,
            statusText: String(result.status),
            headers: {},
            config,
          });
        })) as any,
      getToken: () => 'fake-token',
      onTokenExpired: async () => {
        refreshCalled++;
        await new Promise((r) => setTimeout(r, 50)); // 模拟 refresh 延迟
        return true;
      },
    });

    const requests = Array.from({ length: 5 }, () => sdk.axios.get('/api/test').catch(() => null));
    await Promise.all(requests);

    out.push({
      name: 'A. 并发 5 个请求同时 401, refresh dedupe 只触发 1 次',
      pass: refreshCalled === 1,
      expected: { refreshCalled: 1 },
      actual: { refreshCalled },
    });
    sdk.dispose();
  }

  // ---- B. 5xx 自动重试 ----
  {
    let callIndex = 0;
    const sdk = createSdk({
      baseURL: 'http://fake',
      adapter: ((config: any) =>
        new Promise((resolve) => {
          const i = callIndex++;
          const result =
            i < 2
              ? { status: 503, body: { code: 503, msg: 'service unavailable', data: null } }
              : { status: 200, body: { code: 200, msg: 'ok', data: { i } } };
          resolve({
            data: result.body,
            status: result.status,
            statusText: String(result.status),
            headers: {},
            config,
          });
        })) as any,
      retry: { count: 3, baseDelayMs: 10, maxDelayMs: 50 },
    });

    let success = false;
    try {
      await sdk.axios.get('/api/test');
      success = true;
    } catch {
      success = false;
    }

    out.push({
      name: 'B. 503 重试 2 次后成功',
      pass: success && callIndex === 3,
      expected: { success: true, totalCalls: 3 },
      actual: { success, totalCalls: callIndex },
    });
    sdk.dispose();
  }

  // ---- C. Hooks 钩子触发 ----
  {
    let reqHookCount = 0;
    let resHookCount = 0;
    let errHookCount = 0;
    const sdk = createSdk({
      baseURL: 'http://fake',
      adapter: ((config: any) =>
        Promise.resolve({
          data: { code: 200, msg: 'ok', data: { x: 1 } },
          status: 200,
          statusText: '200',
          headers: {},
          config,
        })) as any,
      hooks: {
        onRequest: () => { reqHookCount++; },
        onResponse: () => { resHookCount++; },
        onError: () => { errHookCount++; },
      },
    });

    await sdk.axios.get('/api/test');

    out.push({
      name: 'C. hooks.onRequest + onResponse 各触发 1 次, onError 不触发',
      pass: reqHookCount === 1 && resHookCount === 1 && errHookCount === 0,
      expected: { reqHookCount: 1, resHookCount: 1, errHookCount: 0 },
      actual: { reqHookCount, resHookCount, errHookCount },
    });
    sdk.dispose();
  }

  // ---- D. 多实例隔离 ----
  {
    let aRefreshCalled = 0;
    let bRefreshCalled = 0;
    const sdkA = createSdk({
      baseURL: 'http://a',
      adapter: ((config: any) =>
        Promise.resolve({
          data: { code: 401, msg: 'Token 已过期', data: null },
          status: 401,
          statusText: '401',
          headers: {},
          config,
        })) as any,
      onTokenExpired: async () => { aRefreshCalled++; return false; },
    });
    const sdkB = createSdk({
      baseURL: 'http://b',
      adapter: ((config: any) =>
        Promise.resolve({
          data: { code: 200, msg: 'ok', data: { y: 2 } },
          status: 200,
          statusText: '200',
          headers: {},
          config,
        })) as any,
      onTokenExpired: async () => { bRefreshCalled++; return true; },
    });

    await sdkA.axios.get('/x').catch(() => null);
    await sdkB.axios.get('/y').catch(() => null);

    out.push({
      name: 'D. createSdk 多实例隔离: A 的 refresh 不被 B 共享',
      pass: aRefreshCalled === 1 && bRefreshCalled === 0,
      expected: { aRefreshCalled: 1, bRefreshCalled: 0 },
      actual: { aRefreshCalled, bRefreshCalled },
    });
    sdkA.dispose();
    sdkB.dispose();
  }

  // ---- E. Plugin 系统: 多 plugin 串行触发 + 异常隔离 ----
  {
    const calls: string[] = [];
    const pluginA = {
      name: 'A',
      hooks: {
        onRequest: () => { calls.push('A.req'); },
        onResponse: () => { calls.push('A.res'); },
      },
    };
    const pluginB = {
      name: 'B',
      hooks: {
        onRequest: () => { throw new Error('B fails on purpose'); },  // 故意抛错验证隔离
        onResponse: () => { calls.push('B.res'); },
      },
    };
    const pluginC = {
      name: 'C',
      hooks: {
        onRequest: () => { calls.push('C.req'); },
      },
    };

    const sdk = createSdk({
      baseURL: 'http://fake',
      adapter: ((config: any) =>
        Promise.resolve({
          data: { code: 200, msg: 'ok', data: { ok: true } },
          status: 200,
          statusText: '200',
          headers: {},
          config,
        })) as any,
      hooks: {
        onRequest: () => { calls.push('opts.req'); },
      },
      plugins: [pluginA, pluginB, pluginC],
    });

    await sdk.axios.get('/api/test');

    // 顺序应是: opts.hooks → pluginA → pluginB(throws, isolated) → pluginC → 然后是响应
    // B 的异常被隔离, A C 仍然能跑到
    const pass =
      calls.includes('opts.req') &&
      calls.includes('A.req') &&
      calls.includes('C.req') &&  // B 抛错没影响 C
      calls.includes('A.res') &&
      calls.includes('B.res');

    out.push({
      name: 'E. Plugin 系统: 多 plugin 串行 + 单 plugin 异常不影响其他',
      pass,
      expected: { hasAll: ['opts.req', 'A.req', 'C.req', 'A.res', 'B.res'] },
      actual: { calls },
    });
    sdk.dispose();
  }

  // ---- F. 内置 logger plugin 工作 ----
  {
    const { loggerPlugin } = await import('../src/plugins/logger');
    const logged: Array<{ level: string; msg: string }> = [];

    const sdk = createSdk({
      baseURL: 'http://fake',
      adapter: ((config: any) =>
        Promise.resolve({
          data: { code: 500, msg: 'boom', data: null },
          status: 500,
          statusText: '500',
          headers: {},
          config,
        })) as any,
      plugins: [
        loggerPlugin({
          level: 'minimal',
          logger: (level, msg) => { logged.push({ level, msg }); },
        }),
      ],
    });

    await sdk.axios.get('/api/boom').catch(() => null);

    // minimal 模式不打 onRequest/onResponse, 只打 onError
    const errorLogs = logged.filter((l) => l.level === 'error');
    const pass = errorLogs.length === 1 && errorLogs[0]!.msg.includes('GET') && errorLogs[0]!.msg.includes('/api/boom');

    out.push({
      name: 'F. loggerPlugin (minimal): 错误时打 1 条 error log, 不打 req/res',
      pass,
      expected: { errorLogs: 1 },
      actual: { allLogs: logged.length, errorLogs: errorLogs.length, firstError: errorLogs[0]?.msg },
    });
    sdk.dispose();
  }

  // ---- G. unauthorized 单飞: 5 个并发 401 (refresh 失败) 只触发 1 次 onUnauthorized ----
  {
    let refreshCalled = 0;
    let unauthorizedCalled = 0;
    const sdk = createSdk({
      baseURL: 'http://fake',
      adapter: ((config: any) =>
        Promise.resolve({
          data: { code: 401, msg: 'Token 已过期', data: null },
          status: 401,
          statusText: '401',
          headers: {},
          config,
        })) as any,
      getToken: () => 'fake-token',
      onTokenExpired: async () => {
        refreshCalled++;
        await new Promise((r) => setTimeout(r, 30));
        return false;  // refresh 失败, 落到 onUnauthorized 兜底
      },
      onUnauthorized: () => {
        unauthorizedCalled++;
      },
    });

    const requests = Array.from({ length: 5 }, () => sdk.axios.get('/api/test').catch(() => null));
    await Promise.all(requests);

    out.push({
      name: 'G. unauthorized 单飞: 5 个并发 401 + refresh 失败 → 1 次 onUnauthorized',
      pass: refreshCalled === 1 && unauthorizedCalled === 1,
      expected: { refreshCalled: 1, unauthorizedCalled: 1 },
      actual: { refreshCalled, unauthorizedCalled },
    });
    sdk.dispose();
  }

  // ---- H. unauthorized 单飞 reset: refresh 成功后, 下一次真未登录仍能触发回调 ----
  {
    let callIndex = 0;
    let refreshResult = true;  // 第一轮: refresh 成功
    let refreshCalled = 0;
    let unauthorizedCalled = 0;
    const sdk = createSdk({
      baseURL: 'http://fake',
      adapter: ((config: any) =>
        new Promise((resolve) => {
          const i = callIndex++;
          // 调用顺序: i=0 第一次请求 401, i=1 refresh 后重放成功;
          // i=2 第二次请求 401, i=3 refresh 后重放仍 401 (因为 refresh 改成 false), 兜底 onUnauthorized
          let result;
          if (i === 0 || i === 2) {
            result = { status: 401, body: { code: 401, msg: 'Token 已过期', data: null } };
          } else if (i === 1) {
            result = { status: 200, body: { code: 200, msg: 'ok', data: { i } } };
          } else {
            result = { status: 401, body: { code: 401, msg: 'Token 已过期', data: null } };
          }
          resolve({
            data: result.body,
            status: result.status,
            statusText: String(result.status),
            headers: {},
            config,
          });
        })) as any,
      getToken: () => 'fake-token',
      onTokenExpired: async () => {
        refreshCalled++;
        return refreshResult;
      },
      onUnauthorized: () => {
        unauthorizedCalled++;
      },
    });

    // 第一轮: refresh 成功, 不应触发 onUnauthorized
    await sdk.axios.get('/api/test').catch(() => null);

    // 第二轮: 把 refresh 改成失败, 应该再触发一次 onUnauthorized (说明 reset 生效)
    refreshResult = false;
    await sdk.axios.get('/api/test').catch(() => null);

    out.push({
      name: 'H. refresh 成功会 reset unauthorized 标记, 下次真未登录仍能触发',
      pass: refreshCalled === 2 && unauthorizedCalled === 1,
      expected: { refreshCalled: 2, unauthorizedCalled: 1 },
      actual: { refreshCalled, unauthorizedCalled },
    });
    sdk.dispose();
  }

  // ---- I. skipAuthPaths: 白名单路径不注入 Authorization ----
  {
    const seenHeaders: Array<Record<string, any>> = [];
    const sdk = createSdk({
      baseURL: 'http://fake',
      adapter: ((config: any) => {
        seenHeaders.push({ ...(config.headers || {}) });
        return Promise.resolve({
          data: { code: 200, msg: 'ok', data: {} },
          status: 200,
          statusText: '200',
          headers: {},
          config,
        });
      }) as any,
      getToken: () => 'fake-token',
      skipAuthPaths: ['/auth/captcha', '/auth/login'],
    });

    await sdk.axios.get('/api/v1/auth/captcha');     // 白名单
    await sdk.axios.get('/api/v1/auth/login');       // 白名单
    await sdk.axios.get('/api/v1/bank/list');        // 业务接口, 应注入 token

    const captchaAuth = seenHeaders[0]?.Authorization;
    const loginAuth = seenHeaders[1]?.Authorization;
    const bizAuth = seenHeaders[2]?.Authorization;
    const pass = !captchaAuth && !loginAuth && bizAuth === 'Bearer fake-token';

    out.push({
      name: 'I. skipAuthPaths: 白名单不注入 Authorization, 业务接口正常注入',
      pass,
      expected: { captcha: undefined, login: undefined, biz: 'Bearer fake-token' },
      actual: { captcha: captchaAuth, login: loginAuth, biz: bizAuth },
    });
    sdk.dispose();
  }

  return out;
}

main().catch((err) => {
  console.error('Test runner crashed:', err);
  process.exit(1);
});
