# Render Book

题本渲染插件，作为 FBA 的应用级插件接入。

当前能力：

- 获取题本模板列表与模板详情
- 校验题本渲染参数
- 创建题本渲染任务
- 查询题本渲染任务
- 将任务请求落盘，便于后续接入 worker 或外部渲染服务

推荐架构：

- FBA 主服务中的本插件负责 API、参数校验、任务编排
- 外部 render worker 或 render service 负责 XeLaTeX 与模板编译

当前接口：

- `GET /api/v1/render-books/templates`
- `GET /api/v1/render-books/templates/{template_key}`
- `POST /api/v1/render-books/jobs/validate`
- `POST /api/v1/render-books/jobs`
- `GET /api/v1/render-books/jobs/{job_id}`

当前内置模板：

- `language_core`
- `quantitative_core`
- `judgment_core`
- `material_digest`
- `exam_paper`
- `wrong_question`

下一步建议：

1. 接入 `backend/core/conf.py` 的更多类型声明与开关控制
2. 将模板定义迁移到数据库或模板配置文件
3. 将本地落盘任务切换为数据库/Redis 队列
4. 接入外部渲染执行器，真正产出 PDF
