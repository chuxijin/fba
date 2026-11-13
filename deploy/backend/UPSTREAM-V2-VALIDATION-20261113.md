# FBA v2 部署准备验证记录

基线：`799daec26f387cd3f552e9535315d3c4f88373e5`。
工作树：`C:/Users/19396/AppData/Local/Temp/opencode/fba-v2-deploy-prep-20261113`。
原始日志/JSON 目录：`C:/Users/19396/AppData/Local/Temp/opencode/`。

## 当前结论

本轮新增 **13 个不同 pytest 用例**已通过，开发 PostgreSQL 升级/回滚/异常数据检查 1 轮通过。未执行全仓测试/构建；未验证 Linux/Python 3.12 目标安装与真实配置 startup，**不能据本报告放行生产**。

复用原项目 `.venv`（Windows/Python 3.14.2），不创建第二套环境、不更改 editable 安装路径。pytest 禁用项目 conftest，强制使用 `.env.example` 假配置、memory broker 和临时 SQLite；不连接生产。

## 实际执行与结论

所有 pytest/Ruff 由临时 runner `fba-v2-prep-validate.py` 执行，保存完整命令、被改文件哈希、基线、退出码、耗时和完整日志。下表中的命令省略固定的 Python 可执行路径。

| 记录 | 最小范围与命令 | 结果 |
| --- | --- | --- |
| `fba-v2-prep-unit-run1` | `python -m pytest --noconftest backend/tests/test_v2_deployment_results.py backend/tests/test_v2_deployment_migration.py` | 11 项：9 通过，2 个 group 用例失败；断言把返回 dict 当 GroupResult，非结果编码失败 |
| `fba-v2-prep-unit-run2` | 仅 results 的 `::test_group_storage_remains_readable_on_rollback`、`::test_group_legacy_pickle_row_is_readable` | 修正为 `['result'].id` 后 2 通过，7.51s；未重跑其余 9 项 |
| `fba-v2-prep-unit-run3` | `python -m pytest --noconftest backend/tests/test_v2_deployment_results.py -k 'not missing_optional_columns'` | decoder 改为识别协议直接读取、新增失败/扩展元数据和无告警用例后，8 通过、1 deselected，8.11s |
| `fba-v2-prep-ruff-run1` | `ruff check --select F --output-format json`：database、conf、迁移、两份测试共 5 文件 | 通过；后续改过的文件由下一记录覆盖 |
| `fba-v2-prep-ruff-run2` | 同命令：仅 database、迁移、results 测试共 3 文件 | 通过，0.11s；conf 和 migration 测试未变，继承 run1 |
| `fba-v2-prep-ruff-run3` | 同命令：仅 `deploy/backend/generate-v2-migration-probe.py` | 通过，0.08s |
| `fba-v2-pg-probe-run1` | `fba_dev.execute_sql` 执行从最终迁移常量生成的 SQL | PostgreSQL 16.13，数据库 fba，角色 chuxijin；最终 result 为通过且 fixture_schema_rolled_back=True |
| `fba-v2-probe-generator-record.json` | 仓库生成器 `--output .../fba-v2-pg-probe-repro.sql`；归一化换行后与已通过 SQL 比较 | 生成成功、内容一致；未重复执行 PostgreSQL 检查 |

pytest 共 **3 轮**；Ruff F 共 **3 轮**；PostgreSQL 检查 **1 轮**；生成器文本一致性检查 **1 次**。未使用 AGY/子代理。

pytest 各轮均报告 221 条 warning，包含现有模型的 SQLAlchemy dataclass default 弃用提示；本轮没有把这些扩大为全仓清理任务，也不声称日志零告警。Git 已跟踪 diff 的 `git diff --check` 通过；新增文件另做文本审阅。环境只读检查 `wsl --list --quiet` 未列出发行版，`Get-Command docker` 未找到可执行文件，未安装依赖或反复尝试启动环境。

run3 重测了 decoder 变更实际影响的 6 个已通过结果/group 用例；这是被测实现修改后的必要验证。缺列用例仅 query 代码的等价排版变化，不使用 decoder，直接继承 run1；迁移 revision/wrapper 未变，继承 4 个 run1 单元用例，最终 SQL 改动则由真实 PostgreSQL 检查覆盖。没有无改动同范围的重复成功测试。

## PostgreSQL 检查覆盖与边界

- 一个事务内创建 `fba_v2_probe_20261113`，只操作该 schema，最终整体 ROLLBACK。没有对开发业务表/生产表执行迁移。
- 旧 enabled 状态映射；旧 INSERT、新 status INSERT、默认 INSERT；新旧字段 UPDATE 同步；非法状态/冲突 NULL 拒绝。
- scheduler args/kwargs 与 opera_log args 的旧 JSON 字符串解包，SQL NULL/JSON null 保留。
- 新结果列添加；菜单启用/原禁用状态和普通菜单范围。
- downgrade 包装旧调度器可读参数，保留升级后新参数、SQL NULL、children/stamps，恢复原菜单状态。
- 错 args 形状、不可解析 JSON 字符串、错 kwargs 形状、错操作日志 args 形状分别失败并回滚，不能留下半迁移 schema/菜单状态。
- 不模拟生产全量数据、表锁等待或长事务，不执行真实 Alembic 连接启动，不覆盖 status-only 新装基线；生产历史数据仍需维护前检查。
- PostgreSQL SQL 检查不等于 SQLAlchemy ORM 的真实 PostgreSQL backend 集成；缺列 savepoint/raiseload 回退通过的是 SQLite 定向测试。Linux/3.12 与目标驱动的实际启动/数据库连接验证仍待完成。

## 最终代码状态（SHA256）

| 文件 | 哈希 |
| --- | --- |
| `backend/alembic/versions/2026-11-13-23_30_00-c5d6e7f8a9b0_upstream_v2_deployment.py` | `95d561bcc48c5cfd2710c150f85bfc03b288f02719db9fe7d207c2f90664809a` |
| `backend/app/task/database.py` | `75662ccf66da1613a191ab8e2a5dd2c2a6a898ed746a1c19c7db22d207277e10` |
| `backend/core/conf.py` | `a0bc73031b22514310eac9dc7aafaed3bbeb9aa444d335b10f1cafef968e02ac` |
| `backend/tests/test_v2_deployment_migration.py` | `273d5c9b9ad415cfa9eb2cecf46c4eab3140f3480b371c36fa586796130a0824` |
| `backend/tests/test_v2_deployment_results.py` | `1fddadbc54db88e4cbe9aaa46a427fe49b16e67cd7d72728361992900f739ab5` |

生成器哈希见 `fba-v2-probe-generator-record.json`；最终 SQL 与迁移对应哈希见 `fba-v2-pg-probe-run1-record.json`。文档改动不触发测试重跑；后续仅在对应代码/配置/测试发生实质改动或平台范围新增时验证最小受影响部分。

## 尚未完成

- 本轮代码提交/合回 dev、推送和生产升级均未执行。
- Linux/Python 3.12 的锁安装、隔离服务 startup 及目标平台认证/ORM集成。
- 新生产快照、恢复预演、维护窗口与排空条件确认。
- 生产执行迁移/菜单调整、精确权限缓存失效、分步启动及受控业务冒烟。

原上游合并的 107 个不同测试已通过且不在本轮无故重跑；详见临时目录 `fba-v2-validation-summary.md`。新准备的 13 个用例与原 107 个分开计数，不能据数量代替发布验收。
