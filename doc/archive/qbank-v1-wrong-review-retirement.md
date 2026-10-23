# V1 错题复盘模块下线归档

## 结论

`backend/app/question_bank` 下的 V1 错题复盘代码已于本次清理中整体删除，接口、模型、CRUD、Service、Schema 均不再存在于运行中的后端。
错题复盘与自主录入错题统一走 `backend/app/question_bank_v2`：

- 提交复盘：`POST /api/v1/qbank-v2/wrong-questions/{wrong_state_id}/reviews`
- 录入外部错题：`POST /api/v1/qbank-v2/wrong-questions/external`
- 复盘数据表：`qbank_v2_question_review`（字段 `summary` + `review_data`）

## 删除的代码

| 原文件 | 说明 |
|---|---|
| `backend/app/question_bank/api/v1/wrong_review.py` | V1 复盘看板、标签、自定义错题、复盘记录接口（`/api/v1/qbank/wrong-review/*`） |
| `backend/app/question_bank/schema/wrong_review.py` | V1 复盘与自定义错题请求/响应模型 |
| `backend/app/question_bank/service/wrong_review_service.py` | V1 复盘业务逻辑 |
| `backend/app/question_bank/crud/crud_wrong_review.py` | V1 复盘/标签/自定义错题数据库操作 |
| `backend/app/question_bank/model/wrong_review.py` | V1 三张表模型：`study_wrong_reason_tag`、`study_wrong_question_custom`、`study_wrong_question_review` |
| `backend/app/question_bank/service/wrong_review_recognition_service.py` | OCR 识别服务，已迁移为 `backend/app/question_bank_v2/service/external_recognition_service.py` |

同时解除的引用：

- `backend/app/question_bank/api/v1/__init__.py` 移除 `/wrong-review` 路由挂载
- `backend/app/question_bank/model/__init__.py` 移除三个 V1 模型导出
- `backend/app/question_bank/model/mastery.py` 移除对 `study_wrong_question_custom` 的外键与关系；`custom_question_id` 列保留为历史列，兼容旧数据
- `backend/app/question_bank/crud/crud_wrong_question.py` 与 V1 错题本查询参数移除 `exclude_reviewed`（依赖 V1 复盘表）

## 数据库表

以下三张 V1 表**保留在数据库中**，仅用于留存历史数据；后端代码已不再读写它们，ORM 也不再声明这些表：

- `study_wrong_reason_tag`
- `study_wrong_question_custom`
- `study_wrong_question_review`

> 由于 ORM 里已没有这些模型，后续用 Alembic autogenerate 对比模型时会倾向于生成删除表的结构迁移；确认不再需要历史数据前，不要把这类迁移直接应用到生产库。

确认历史数据无需保留后，可手工执行（不会自动执行，也不会随迁移运行）：

```sql
DROP TABLE IF EXISTS study_wrong_question_review;
DROP TABLE IF EXISTS study_wrong_question_custom;
DROP TABLE IF EXISTS study_wrong_reason_tag;
```

> 注意：`study_mastery_status.custom_question_id` 是历史列，如需彻底清理，应在确认无历史数据依赖后再单独评估删除。

## 需要找回旧实现时

删除已进入提交历史后，可用下面的命令恢复任意一个文件：

```bash
git checkout <删除前的提交> -- backend/app/question_bank/model/wrong_review.py
```

三张表的建表结构也可从该文件对应的 SQLAlchemy 模型或历史迁移中还原。

## 为什么不再保留 V1 实现

- 小程序、管理端、Web 端已全部改用 V2 接口，V1 复盘接口没有调用方；
- V1 复盘与 V2 复盘字段语义不一致（V1 只有 `summary`，没有「正确思路」），保留会让每次排查都多读一套死代码；
- 代码历史可通过本文件的表格与 Git 记录找回，不需要把死代码留在 `backend/app`。
