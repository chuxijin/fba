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

Command Code (cmdc) 协同调用规则
定位：本地后台执行工人，专接耗时、无脑、机械的体力活（主控负责架构与核心决策）
调用指令：cmdc -p "<任务指令与汇报要求>" -m deepseek/deepseek-v4.1-flash --yolo
适用场景（下放）：
1. 耗时测试与门禁：全量回归测试套件，让其后台跑并只汇报最终结论与失败摘要，杜绝刷屏阻塞
2. 错误自愈：批量 TS 类型报错（typecheck）、Lint 报错修复，让其自动边修边跑直到清零
3. 机械重构：全仓跨文件废弃 API/旧组件批量替换、多环境配置项对齐补全
4. 样板与数据：批量单测用例扩充、大型 JSON/Mock 夹具生成、批量补全 JSDoc
5. 代码大扫除：全仓死代码、未使用的导入（unused import）、残留 console.log 清理
严禁下放：支付/鉴权核心链路、高并发与事件竞态逻辑、数据库 DDL/迁移、重大架构决策
