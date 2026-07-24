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