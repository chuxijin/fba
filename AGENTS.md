本地 Python 环境
全局 Python 由 pyenv-win 管理，当前版本 3.12.12
已配置 uv，项目场景优先使用 uv run、uv sync、uv venv 指令，零散全局操作直接使用 python、pip

本地文件操作（FastCtx）
读取、搜索、查找文件：优先调用 mcp__fastctx__read、mcp__fastctx__grep、mcp__fastctx__glob，禁止使用 cat、rg、ls -R 等命令
调用工具必须传入绝对路径；返回结果末尾会标注 Complete 或 Partial，出现 Partial 标识时，需要依照提示参数接续获取剩余内容
批量文本替换：使用 mcp__fastctx__replace，该工具可保留文件编码与换行格式，支持试运行 dry-run，写入文件前会拦截并发修改操作
语义化改写、局部代码改动使用 apply_patch，机械式全局替换使用 replace 工具

 MCP 工具调用规则
网络搜索：首选 tavily-hikari；网页内容抓取选用 tavily_extract、tavily_crawl，以上工具无法使用时，降级调用内置搜索工具
登录生产服务器：ssh MCP 工具
查询操作开发环境数据库：fba_dev
查询操作生产环境数据库：fba_prob

skill调用规则
FBA 后端业务相关 → fba skill
管理端前端项目相关 → antdv-next skill
小程序项目相关 → wot-ui 相关skill

Antigravity CLI (agy) 协同调用规则
定位：本地后台执行工人，专接耗时、无脑、机械的体力活（主控负责架构与核心决策）
调用指令：agy -p "<任务指令与汇报要求>" --model gemini-3.8-flash-low --dangerously-skip-permissions

【硬性规则（必须遵守，非建议）】
- 主控 Agent 一律不得直接运行测试/门禁类命令（pytest、vitest、pnpm test、npm test、uv run pytest、typecheck、lint、全量回归等），必须通过 agy 下放，只接收最终结论与失败摘要。
- 判断顺序：先判断任务是否命中下方"适用场景" → 命中则强制走 agy，不得以"顺手/更快"为由自己执行。
- 仅当 agy 不可用（报 command not found / 执行失败）时，才允许主控直接运行，且必须在回复中说明该异常。
- 支付/鉴权核心链路、高并发与事件竞态、数据库 DDL/迁移、重大架构决策仍由主控亲自处理，不下放。

执行方式（关键，决定快慢）：
- 下放一律用"后台/异步"方式启动（shell 工具的 background 模式），不要前台干等。
- 启动后主控立刻继续做"不依赖测试结果"的其他工作；等 agy 完成通知后再汇合、取回结论。
- 目的：让测试耗时与主控工作耗时重叠（并行），而不是相加（串行）。
- 汇合后再统一决策，不要为了早看结果而轮询/poll。

适用场景（下放）：
1. 耗时测试与门禁：回归测试（包括全量）套件，后台跑，只汇报最终结论与失败摘要，杜绝刷屏阻塞
2. 错误自愈：批量 TS 类型报错（typecheck）、Lint 报错修复，自动边修边跑直到清零
3. 机械重构：全仓跨文件废弃 API/旧组件批量替换、多环境配置项对齐补全
4. 样板与数据：批量单测用例扩充、大型 JSON/Mock 夹具生成、批量补全 JSDoc
5. 代码大扫除：全仓死代码、未使用的导入（unused import）、残留 console.log 清理

严禁下放（主控亲自处理）：
- 支付/鉴权核心链路
- 高并发与事件竞态逻辑
- 数据库 DDL/迁移
- 重大架构决策

例外（此情形不下放，主控直接跑）：
- 秒级、输出很小的单项检查（单个测试文件、单条 lint），下放开销反而更大
- 必须看原始堆栈/逐行日志才能定位的问题
