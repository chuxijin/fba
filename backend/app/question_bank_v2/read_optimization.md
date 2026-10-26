# 错题读取与批量录入优化

## 固定响应视图

`GET /api/v1/qbank-v2/wrong-questions` 沿用同一套筛选、排序和游标分页：

| view | 用途 | 每条响应字段 |
| --- | --- | --- |
| `full`（默认） | 兼容原列表调用 | 原有完整列表字段 |
| `summary` | 小程序错题卡片 | `id`、`section_name`、`stem_preview`、`status`、`wrong_count`、`review_count` |
| `outline` | 答题卡与题号导航 | `id`、`section_name` |

- 摘要最多 160 字及省略号；原始题干仍由完整列表／单题详情提供。
- `summary` 只选择生成摘要与状态所需的列；SQL 内部 `_stem` 生成一次 `stem_preview`，响应验证不再去标签，保留解码后的比较符。
- `outline` 不读取题干，也不联查掌握度。SQL 保留游标需要的排序键，响应 Schema 过滤这些内部字段。
- 列表和章节接口通过 `WrongQuestionFilters` 共用参数，用户身份仍由鉴权请求提供；领域子树由服务解析。
- 待复盘、统计与集合复用同一个待复盘表达式。已复盘浏览与跨状态复盘档案仍使用各自口径。
- 导入批次、散题和集合响应复用 `CursorPageData[T]`，保留原分页字段和默认值。

## 取数与写入

- 单条和批量录入共用 `_capture_external` 写入核心，返回 `question_id`／`wrong_state_id`。
- 单条接口在写入后装配一次详情；批量直接组装成功记录，不逐题读取详情、错误历史、用户偏好和材料。
- 批量录入只解析一次记录领域；材料缓存只接纳已释放 savepoint 的成功条目，失败条目新增的引用不会流入后续条目。
- 最近错误答案使用相同用户／题目范围及稳定时间、ID 倒序，数据库 `LIMIT 1`；仅排除 JSON 布尔 `true` 的背题浏览标记。
- 已复盘题的移出阈值固定为 1，详情不再查询无用的用户偏好；首次复盘前仍读取用户阈值。

## 验证与样本

功能回归执行真实内存 SQLite SQL、sqlakeyset 分页及 FastAPI 请求／响应验证：

```powershell
uv run --no-sync pytest -q -s --disable-warnings --confcutdir=backend/app/question_bank_v2/tests backend/app/question_bank_v2/tests/test_wrong_browse.py backend/app/question_bank_v2/tests/test_wrong_read_optimization.py backend/app/question_bank_v2/tests/test_review_service.py backend/app/question_bank_v2/tests/test_wrong_domain_scope.py backend/app/question_bank_v2/tests/test_service_contract.py
```

小程序在 `mini` 中执行真实页面和微信模板测试：

```powershell
node --test --test-reporter=spec tests/wrong-browse-page.test.cjs tests/wrong-review-page.test.cjs tests/review-sheet.test.cjs
```

相同 5 道长题干、相同范围，使用实际 JSON 响应编码器的未压缩样本：

| 响应 | 字节数 |
| --- | ---: |
| full | 86,672 |
| summary | 3,034 |
| outline | 274 |

50 道批量录入不再执行原本每题 4 次的详情装配读取，共省掉约 200 次展示查询；验证同时覆盖单条返回契约、部分失败及材料缓存隔离。上述字节数为合成样本，不等同于所有线上响应的固定比例；线上耗时还取决于题干、数据库和网络。
