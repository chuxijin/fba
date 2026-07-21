# Render Book

题本渲染插件，作为 FBA 的应用级插件接入。

当前能力：

- 获取题本模板列表与模板详情
- 校验题本渲染参数
- 基于真实题库数据生成标准化渲染 payload
- 创建题本渲染任务
- 查询题本渲染任务
- 将任务请求与 `payload.json` 落盘，并同步保存任务/文件元数据，便于后续接入 worker、OSS 或外部渲染服务
- 支持手动触发外部 `render_pdf` 执行器，按渲染变体拉取 PDF 产物并上传到 OSS

统一导出协议：

- `content_mode`
  - `questions_only`
  - `questions_with_answers`
- `answer_layout`
  - `inline`
  - `appendix`
- `delivery_mode`
  - `single_pdf`
  - `split_pdf`

推荐组合：

- `questions_only`
  - 仅题目，固定输出单个 PDF
- `questions_with_answers + inline + single_pdf`
  - 题目和解析同册，解析紧跟每题
- `questions_with_answers + appendix + single_pdf`
  - 题目和解析同册，解析集中排版
- `questions_with_answers + appendix + split_pdf`
  - 题目册、解析册分开输出

兼容说明：

- 旧字段 `solution_mode`、`output_targets`、`render_variants` 仍然保留
- 新协议会优先生效
- 执行层内部仍复用旧 `render_variants`，以降低上线风险

请求示例：

```json
{
  "template_key": "exam_paper",
  "title": "2026 模拟卷",
  "content_mode": "questions_with_answers",
  "answer_layout": "appendix",
  "delivery_mode": "split_pdf",
  "filters": {
    "bank_id": 61,
    "question_count": 100
  }
}
```

推荐架构：

- FBA 主服务中的本插件负责 API、参数校验、任务编排
- `templates/<template_key>/<version>/` 是模板源码的唯一来源
- 外部 render worker 或 render service 负责 XeLaTeX 与模板编译
- 部署时以只读目录或版本化发布产物向执行器挂载模板
- 每个任务固定 `template_version` 和 `template_digest`，执行前校验内容一致性

当前接口：

- `GET /api/v1/render-books/templates`
- `GET /api/v1/render-books/templates/{template_key}`
- `POST /api/v1/render-books/jobs/validate`
- `POST /api/v1/render-books/jobs/payload-preview`
- `POST /api/v1/render-books/jobs`
- `POST /api/v1/render-books/jobs/{job_id}/execute`
- `GET /api/v1/render-books/jobs/{job_id}`

当前数据流：

- `question_bank` 等业务表负责提供真实题目、选项、解析、材料、挂载信息
- `render_book` 插件负责把数据库结构整理成统一的 `RenderDocumentPayload`
- `render_book` 插件负责维护渲染任务表、渲染文件表，并可复用 `oss` 插件上传 PDF
- 外部 `render_pdf` 服务只消费统一 payload，不直接理解业务数据库
- 执行阶段由 `render_book` 调用 `render_pdf`，按 `render_variants` 拉取 PDF/log 产物并回写任务状态

当前内置模板：

- `exam_paper`
- `practice`
- `wrong_question`
- `basic_calculation`
- `hanyu`

模板发布约束：

- 已发布版本不可原地修改；变更模板时新增版本目录
- 版本号使用 `x.y.z` 格式，例如 `1.1.0`
- `manifest.toml` 的 `key`、`version` 必须与目录名一致
- 执行器的 `RENDER_SERVICE_TEMPLATES_ROOT` 必须指向同一份只读发布产物

下一步建议：

1. 接入 `backend/core/conf.py` 的更多类型声明与开关控制
2. 将当前数据库任务进一步接入 Celery/Redis 队列执行
3. 将版本化模板目录发布到制品库或对象存储
