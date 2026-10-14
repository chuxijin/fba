# backend/scripts 目录索引

本目录已按「**业务领域 + 使用频度**」重新分类。原先 58 个脚本平铺在根目录，现在全部归入子目录，
根目录只保留分类文件夹。

> **执行约定**：所有脚本都以**仓库根目录**为工作目录执行，例如
> `uv run python backend/scripts/dev/dump_openapi.py`。
> 少数脚本支持模块方式调用，见下方各表「调用方式」列。

## 目录结构

| 目录 | 用途 | 频度 |
|---|---|---|
| `dev/` | 开发工具链：格式化、CI 门禁、SDK 生成 | 🔥 高频 |
| `qbank/import/` | 题库数据导入 | ♻️ 按需 |
| `qbank/export/` | 题库数据导出为 Excel | ♻️ 按需 |
| `qbank/audit/` | 题库审计、图片镜像、向量化 | ♻️ 按需 |
| `qbank/label/` | AI 知识点自动标注 | ♻️ 按需 |
| `paper/` | 题本 / 试卷 / 题卡 / 素材生成 | ♻️ 按需 |
| `seed/` | 菜单、角色、初始配置录入（幂等） | ♻️ 按需 |
| `migration/` | 数据迁移与回填 | ⚠️ 一次性为主 |
| `diag/` | 诊断、冒烟、性能基准 | ♻️ 按需 |
| `kaoyantu/` | 考研兔数据专用流程（自带 README） | ♻️ 按需 |
| `yunyxzx/` | 云逸之舟数据专用流程（自带 README） | ♻️ 按需 |
| `vocab_data/` | 词书数据文件 + 词书导入脚本 | ♻️ 按需 |
| `archive/` | **已失效或已完成的一次性脚本**，仅作追溯 | 💀 归档 |
| `outputs/` `logs/` | 脚本产物与日志（已被 `.gitignore` 忽略） | — |

**图例**：🔥 高频（改动会影响 CI/他人） · ♻️ 可复用（幂等或有参数，按需重跑） ·
⚠️ 一次性（通常已执行完） · 💀 归档（不再维护）

## 新增脚本放哪里

1. 先判断**业务领域** → 选 `qbank/` `paper/` `seed/` `migration/` `diag/`，或新建领域目录。
2. `qbank/` 内部按**动作**再分 `import/` `export/` `audit/` `label/`。
3. 若脚本被其它脚本 `import`（是「库」而非「入口」），在下方表格里标注 `★库`，
   移动它时必须同步修改调用方。
4. 写完脚本后**在本 README 对应表格补一行**。

---

## dev/ — 开发工具链 🔥

| 脚本 | 说明 | 调用方式 |
|---|---|---|
| `lint.sh` | prek 全量格式化检查 | CI `lint.yml` 直接调用，路径已同步 |
| `format.sh` | `ruff format --preview` | `bash backend/scripts/dev/format.sh` |
| `export.sh` | `uv export` 生成 requirements.txt | `bash backend/scripts/dev/export.sh` |
| `quality.sh` | 完整质量门禁（ruff + bandit + pytest + mypy + radon） | 本地用，**已被 .gitignore 忽略**（未入库） |
| `dump_openapi.py` | 不启服务 dump OpenAPI JSON，驱动前端 SDK 生成 | `python backend/scripts/dev/dump_openapi.py` |

> `dump_openapi.py` 是前端 SDK 同步链路第一步，见 `packages/api-sdk/SYNC.md`。

## qbank/import/ — 题库导入 ♻️

| 脚本 | 说明 |
|---|---|
| `import_gongkao_seed.py` | 公考申论 seed 导入（`enrich` 补解析 / `papers` 导整卷，默认 dry-run） |
| `import_gongkao_shizhen_content.py` | 公考时政内容导入 |
| `import_papers_to_v2.py` | 国考行测试卷导入本地 V2（按卷建库、item_key 去重） |
| `qbank_import_console.py` | **交互式导入控制台**，题库导入主力工具（体量最大） |
| `qbank_import_saduck_shenlun.py` | 「傻豆」申论题库导入 |

## qbank/export/ — 题库导出 ♻️

| 脚本 | 说明 |
|---|---|
| `export_bank_to_excel.py` | 按 `--bank-id` / `--cat-id` 导出 V2 格式 XLSX |
| `export_gwy_xc_papers.py` | 国考行测各年份试卷导出为**独立** XLSX（按卷分组） |
| `export_gwy_xc_to_excel.py` | 国考行测导出为**单个** V2 XLSX（按章节分组） |
| `export_import_gwy_sl.py` | 国考申论「导出 → 导入 → 复制到业务目录」一条龙 |

## qbank/audit/ — 审计与媒体 ♻️

| 脚本 | 说明 |
|---|---|
| `qbank_image_mirror.py` | **★库** 图片镜像到对象存储。被 `qbank_import_console` / `qbank_mirror_existing_images` / `qbank_import_saduck_shenlun` 共 3 处 import |
| `qbank_mirror_existing_images.py` | 存量题目图片批量镜像（依赖上者） |
| `qbank_formula_image_audit.py` | 公式图片审计（产出 CSV 报告） |
| `qbank_formula_image_replace.py` | 公式图片批量替换 |
| `qbank_bank_code_audit.py` | 题库 code 规范审计 |
| `qbank_vectorize_questions.py` | 题目全量向量化（支持断点续跑、限速）。`python -m scripts.qbank.audit.qbank_vectorize_questions` |

## qbank/label/ — AI 标注 ♻️

| 脚本 | 说明 |
|---|---|
| `qbank_autolabel_knowledge_points.py` | AI 知识点自动标注，`chat` / `jev` 双引擎。线上能力已迁入 `backend/app/question_bank_v2/service/ai_label_service.py`，**本脚本保留作对照工具** |

## paper/ — 题本 / 试卷生成 ♻️

| 脚本 | 说明 |
|---|---|
| `gongkao_question_generator.py` | **★库** 公考速算与资料分析题目生成引擎，被 `generate_all_50_days.py` import |
| `generate_spatial_cube_patterns.py` | **★库** 空间立方体图案资源生成，被 `publish_spatial_cube_patterns.py` **及 `backend/app/study_plan/tests/` 单测** import |
| `publish_spatial_cube_patterns.py` | 把生成的图案发布到对象存储 + 数据库 |
| `generate_all_50_days.py` | 批量生成 50 份行测速算题卡（docx + PDF） |
| `generate_full_comprehensive_pack.py` | 全套速算 + 资料分析题卡生成 |
| `generate_exam_paper_template.py` | 考场真卷「封面 + 注意事项 + 正文」全流程 docx 生成 |

## seed/ — 后台初始化（幂等，可重复跑） ♻️

| 脚本 | 说明 |
|---|---|
| `insert_feishu_sheets_menu.py` | 录入「我的网盘 / 飞书表导出」菜单 |
| `insert_qbank_ai_autolabel_menu.py` | 录入「AI 自动标注」菜单 |
| `insert_question_generation_menu.py` | 录入「题目生成」菜单 |
| `insert_study_handbook_menu.py` | 录入「学习手册」菜单 |
| `insert_study_plan_menu.py` | 录入「学习规划」菜单 |
| `bind_study_plan_roles.py` | **★库** 创建学习规划角色并绑定菜单权限，被 `prepare_study_plan_e2e.py` import |
| `prepare_study_plan_e2e.py` | 准备真实账号端到端联调数据（依赖上者） |
| `instantiate_plan_for_user.py` | 为指定用户实例化一份学习规划模板 |
| `configure_data_analysis_first_level.py` | 配置挑战模块「资料分析」一级分类 |
| `configure_data_analysis_second_level.py` | 配置挑战模块「资料分析」二级分类 |
| `import_sensitive_words.py` | 导入 Sensitive-lexicon 精选敏感词 |

> 所有 `insert_*_menu.py` 均用 `WHERE NOT EXISTS` 实现幂等，重复执行不会插重复行。

## migration/ — 迁移与回填 ⚠️

> 目录名不用 `data/`，因为 `.gitignore` 有一条裸 `data/` 规则会匹配任意层级，会把这里的脚本静默排除出 git。

| 脚本 | 说明 | 状态 |
|---|---|---|
| `apply_kaoyan_knowledge_system.py` | 新建「考研政治」知识体系版本 + 知识点树 | 较新，可能仍需使用 |
| `backfill_qbank_v2_knowledge_mastery.py` | 从历史作答回填知识点掌握度（幂等，迁移后执行） | ♻️ 可复用 |
| `backfill_shenlun_projection.py` | 补做历史申论 Agent 成功运行的题库 V2 投影 | 一次性 |
| `migrate_v1_to_v2.py` | 题库 v1 → v2 数据迁移 | ⚠️ 已完成 |
| `migrate_ziliao_2026.py` | 生产 2026 资料分析 ↔ 开发库同步 | ⚠️ 一次性 |

## diag/ — 诊断 / 冒烟 / 基准 ♻️

| 脚本 | 说明 |
|---|---|
| `bench_api.py` | API 响应时间批量检测（需传 JWT token） |
| `bench_qbank_scope.py` | qbank 学习领域接口性能对比（支持并发模拟） |
| `inspect_shenlun_quota.py` | 查询 Redis 里的申论配额计数与 TTL |
| `openlist_sync_diag.py` | OpenList 同步链路诊断 |
| `smoke_shenlun_agent.py` | 申论批改真实链路冒烟（开发环境） |
| `smoke_shenlun_coach.py` | 申论教练会话冒烟 |
| `test_hanyu_frequency.py` | 汉语词频统计任务测试 |

## 领域自包含目录

| 目录 | 内容 |
|---|---|
| `kaoyantu/` | 考研兔：`extract_kaoyantu_from_burp.py`（解析抓包）、`import_to_v2.py`（导入）、`export_kaoyantu_questions_excel.py`（接口导出）。**详见其 README.md** |
| `yunyxzx/` | 云逸之舟：`import_yunyxzx_paper.py` + 两个解析修复脚本。**详见其 README.md** |
| `vocab_data/` | 词书 zip 数据 + `vocab_import_kajweb.py`（从 kajweb/dict 导入词书）+ `inspect.py` |

## archive/ — 归档 💀

以下脚本已失效或任务已完成，保留仅供追溯，**不建议再执行**：

| 脚本 | 归档原因 |
|---|---|
| `analyze_questions.py` | 「国考言语理解真题分析」临时任务；输入 `backend/output/gk_yuyan_2019_2026.md` 已不存在 |
| `deep_analyze.py` | 同上，是 `analyze_questions.py` 的进化版，两者输入输出相同（互相取代） |
| `export_gk_yuyan.py` | 同上链路的第一步：把 MCP 输出的 JSON 转 Markdown 供前两者消费 |
| `organize_daily_schedule.py` | 50 天特训产物排期；已被 `reorganize_by_daily_folder.py` 取代 |
| `reorganize_by_daily_folder.py` | 同上任务的最终版，一次性产物整理 |

---

## 维护记录

- **2026-10-11**：目录重建。58 个平铺脚本归入 9 个分类目录；
  删除与 `kaoyantu/extract_kaoyantu_from_burp.py` 完全重复（md5 一致）的根目录副本；
  同步修复 31 处文件内路径锚点、5 处跨脚本 `backend.scripts.*` 导入、
  以及 CI / 文档 / .gitignore / 单测中的 10 余处引用。
