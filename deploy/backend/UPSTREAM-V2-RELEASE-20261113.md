# FBA v2.0.0 发布与回滚手册

状态：**本地准备已完成，生产仍为 NO-GO**。本文不是生产执行授权。

本轮未推送、未安装生产依赖、未改生产数据库/配置、未清缓存、未停止或重启服务。

## 1. 本次交付

- 迁移 `c5d6e7f8a9b0`，前驱为生产当前 `b4c5d6e7f8a9`。
- 调度表保留 `enabled`，新增 `status`；双向 BEFORE trigger 和 CHECK 约束保持 0/1 与布尔值一致。旧 enabled 写入、新 status 写入及省略状态的 INSERT 都可处理。新 status 更新优先同步旧字段；不要在同一次写入中提供相互矛盾的新旧状态。
- status 不设置数据库默认值，以便触发器识别旧 INSERT；enabled 默认 true。新 ORM 提供 status，触发器在 NOT NULL 检查前补齐 enabled。已有非法/不一致状态导致迁移失败，而不是自动猜测状态。
- 调度 args/kwargs、操作日志 args 转为 JSONB。解包一层旧 JSON 字符串，分别校验 array/object/object 或 null；所有行（包括逻辑删除行）都参与转换。SQL NULL 与 JSON null 分别保留。非法字符串/形状使整笔迁移回滚，不输出业务参数、不静默丢弃历史记录。
- 结果表补 nullable bytea `children` / `stamps`；不改写既有结果字节。
- 备份匹配代码生成器的菜单 ID/原 status 后禁用入口，不删除菜单或角色绑定。
- 默认 `CELERY_RESULT_LEGACY_PICKLE_WRITE=True`，task/group 结果使用 protocol 4 pickle，旧 PickleType ORM 可读。args/kwargs 仍使用原 serializer，新增 children/stamps 使用配置 serializer。
- 缺列 SELECT 使用 savepoint，回退查询 defer 两个可选列并禁止 lazy load。**只保证降级读取，不承诺缺列时新结果 INSERT/UPDATE 成功；生产必须先迁移再启动新 worker。**
- 识别旧 pickle 协议后直接读取，避免每次兼容读取都产生预期内告警。pickle 仅允许来自可信结果数据库，不能用于外部不可信输入。

验证范围/命令/哈希见 `UPSTREAM-V2-VALIDATION-20261113.md`。

## 2. 放行前必须满足

1. [ ] 在经批准的隔离 Linux/Python 3.12 环境验证目标锁、安装和关键入口。Windows/3.14 的结果不能替代它。本机未发现可用 WSL 发行版；不自动安装、建立第二套本地 .venv 或在运行中的生产 .venv 试装。
2. [ ] 确认生产 uv 0.7.20 能读取目标 uv.lock；若不支持，单独批准工具升级并备份原 uv，不临时重新解析依赖或修改目标锁。
3. [ ] 明确发布 commit、目标依赖清单和维护窗口；当前隔离工作树改动未提交/合回，不能拿基线 `799daec2` 作为包含本修复的版本发布。
4. [ ] 本次生产库备份、恢复预演和原环境恢复材料均已可用；5 月的旧备份不满足本次发布要求。
5. [ ] 确认暂停入口、外部 webhook 重试/幂等策略和任务排空标准。支付/鉴权、运行中的文件同步任务不能靠强杀或丢消息处理。
6. [ ] 生产再次只读核对：实际数据库/schema、search_path、当前 revision、表大小、长事务/锁、任务状态/JSON 类型及菜单匹配范围。首次探测操作日志只采样了 200 行，不代表历史全表一定可转换。

### Linux 隔离验证边界

- 使用用户批准的既有测试环境或临时容器；不得消费生产 RabbitMQ vhost `fba_prod`，不得连接生产 DB/Redis。
- 只使用假配置/测试服务；不导入后直接启动 lifespan、beat 或 worker 连接真实业务环境。
- 原样安装目标锁和插件依赖，记录 Linux/Python/uv、包版本与安装日志；不重新生成 uv.lock/requirements.txt。
- 最小验证包含 Settings 构造和安全配置结果、FastAPI 路由构造、Celery 应用/结果 backend、现有定向兼容测试。真实 startup 依赖隔离 DB/Redis 时，只有批准并具备这些服务后才能启动；导入成功不等于 startup 成功。
- 四端认证协议继续继承已有测试结论；Linux 测试的理由是运行平台改变，不扩大为全仓回归。

## 3. 维护窗口步骤（逐项确认后执行）

生产命令通过 SSH MCP **一条一步执行**，不使用 `&&` 或把部署、迁移、重启串成一次调用。所有敏感备份保存在仅管理员可读目录，报告只记路径/时间/大小/校验，不能打印密码或 token。

### A. 保存基线与排空

1. 记录 Git head/status、Supervisor 状态、队列和错误基线；保护生产已有 4 个未跟踪备份文件。若存在新的已跟踪修改，停止并确认，不 reset/clean。
2. 创建本次受限备份目录；保存原源码/锁/包清单、生产 `.env`、Supervisor 配置、uv 版本及完整原 `.venv` 的可还原归档。保留原路径，确保还原后 shebang/editable 路径仍指向 `/www/wwwroot/WeBot`。
3. 在批准的入口层进入维护模式并停止新增任务派发；确认支付/外部 webhook 可可靠重试。单独停止 beat：

   ```bash
   sudo -n supervisorctl stop fba:fba_celery_beat
   ```

4. 保持 worker 消费已入队任务，核对其实际消费队列。分别看 active、reserved、scheduled 与 RabbitMQ ready/unacked；单次 unacked=0 不算排空。长期 ETA/孤立队列必须明确保留和重新接续方案。
5. 确认安全排空后单独停止 API、worker、Flower。worker 使用正常优雅停止，核对 stopwaitsecs；到时仍有任务则中止发布，不强杀、不 purge。
6. 此时统一 `.venv` 的所有使用者均已停止，才允许覆盖依赖。不要只停 API，留下旧 worker/beat 继续使用正在修改的环境。

### B. 创建可恢复快照

7. 使用既有安全认证创建完整 `fba` custom-format pg_dump，覆盖 schema、业务数据及 Alembic 状态；保存角色/扩展恢复前提。
8. 记录备份退出码、时间、大小和 SHA256；`pg_restore --list` 只证明清单可读，**不等于恢复验证**。在隔离数据库实际恢复并核对 revision、关键表行数、数据/扩展和权限。
9. 若本次备份/恢复失败或超出维护窗口，恢复旧服务/派发并退出发布，不继续升级。未恢复验证前不声称可安全回滚。

### C. 依赖与迁移

10. 按批准的 commit 拉取代码，核对最终 hash/干净状态。此时目标必须含本轮修复；保留 .env 和旧备份，不覆盖成 .env.example。
11. 使用批准的 uv 及原 Python 3.12，在**原 `.venv`**按锁同步所需生产依赖。生产原 dev/group 使用范围先记录，不凭猜测删组；命令以隔离预演成功的形式为准，例如经确认的 `uv sync --frozen --no-dev`。不得不带 frozen 重新解析、只升级几个包或先覆盖运行中环境。
12. 仅检查脱敏配置：ENVIRONMENT=prod 的有效 RabbitMQ/vhost、数据库/schema/Redis 地址、TOKEN 算法/有效期/会话前缀、结果 serializer；显式确认 `CELERY_RESULT_LEGACY_PICKLE_WRITE=True`。保留原 TOKEN_SECRET_KEY/HS256、cookie 和 Redis 会话数据。生产配置若曾显式关闭 legacy 开关，必须先单独确认，不依赖代码默认值。
13. 确认 Alembic 的实际 search_path 能解析 `fba.task_scheduler` 和 `fba.alembic_version`。迁移按可见 task_scheduler 所在 schema 操作其余表；路径缺失/错误时停止，不能让它迁移另一个同名 public 表。
14. 在 backend 工作目录使用新依赖执行精确 revision：

   ```bash
   uv run --no-sync alembic upgrade c5d6e7f8a9b0
   ```

   迁移按 revision 一个事务执行；lock_timeout=5s、statement_timeout=5min。ACCESS EXCLUSIVE 锁和 JSONB 重写可能持锁较久，不能承诺零停机。锁等待或形状校验失败时事务回滚，保留异常类别/行 ID，再确认 revision 和 schema；不得无脑重试或临时增加超时。
15. 只读核对 revision、新列/触发器/约束、所有调度状态一致性、参数形状、菜单备份范围与禁用情况。启用调度基线为 23 条，以刚保存的维护窗口快照为准。
16. 菜单/角色权限缓存只能清计算缓存：`JWT_USER_REDIS_PREFIX:<数字用户ID>`（默认 `fba:user:<ID>`），或按备份 menu IDs 调用 `user_cache_manager.clear_by_menu_id`。若新旧关系缓存格式不兼容，清所有此精确数值 ID 键。**禁止 `DEL fba:user:*`、FLUSHDB/FLUSHALL 或删除 token/refresh/session/锁键**；`fba:user:lock:*` 不是权限缓存。升级和回滚都执行对应受控失效步骤，操作前先核对有效前缀。

### D. 分步启动和验收

17. 分别启动 API、worker，核对启动/数据库/插件日志及 worker 消费队列；失败时不启动 beat、不解除维护模式。
18. 完成受控只读冒烟：保护 API 的统一 401 `data.auth_reason` / `data.refreshable`，旧 access/refresh 与一次严格轮换、四端会话隔离；用户使用已批准的测试账号，不导出 token。题库/会员/支付订单采用查询或测试方式，不创建真实扣款、不重放生产任务。
19. 按批准方案测试一个不带真实业务参数的无副作用任务结果及 group，再单独启动 Flower、最后启动 beat；核对调度状态/参数、任务接续与新增错误。没有安全测试任务时不要临时用支付/文件同步任务代替。
20. 对比维护前后的错误/资源指标和配置，不把 RUNNING 等同业务正常；确认后解除维护模式并观察。Flower read-only 等附加配置作为独立批准项，不顺手修改。

## 4. 回滚分支

### 迁移未成功或尚未启动新业务

- 保持派发停止，确认 `b4c5d6e7f8a9` 及旧 schema；失败迁移应整体回滚，但需查证。
- 干净 Git 使用非强制版本切换到旧 commit `e7670efd15191a934bddc30040e463384122be4a`，或从事先准备的旧源码归档恢复；不使用 hard reset/clean，不碰未知修改。
- 从完整原环境归档恢复同路径 `.venv`、原配置及 uv。仅回 Git 或让新锁再次 uv sync 不能恢复旧依赖。
- 分步启动旧 API/worker/Flower，检查后启动旧 beat，再解除维护模式。

### 迁移已成功（包括新版本已写入）

1. 重新暂停入口/派发、停止 beat，按同样标准排空新 worker 并停止所有环境使用者；记录升级以来的新任务、参数和菜单变更。
2. **先用仍保留的新代码/依赖执行精确 downgrade**，旧源码没有本次 revision，不能先切旧代码再 downgrade：

   ```bash
   uv run --no-sync alembic downgrade b4c5d6e7f8a9
   ```

3. downgrade 同步最新 status → enabled，删除本次状态约束/trigger/status；调度数组/对象重新包装为旧代码 `json.loads` 可读的 JSON 字符串，保留新参数与 null；操作日志 args 转回 json。
4. 恢复备份菜单状态（仅当前仍为 0 的原匹配菜单）；新菜单/角色绑定不删除，升级后人工变更需另外核对。`children`/`stamps` 保留以免丢新元数据；旧 ORM 不读取它们。备份表仅在完成恢复后删除。
5. 确认 legacy 开关始终为 True，保存的新 task/group 结果可被旧 PickleType 读取。**如果期间关闭过开关，新 serializer 字节可能不被旧 ORM 接受：暂停回滚自动流程，先隔离识别/转换相关新行并验证；不能清空结果表解决。**
6. 清精确用户权限计算缓存，切旧源码并恢复完整原环境/配置，再分步启动和核对旧调度/任务/会话。回滚后不能重放已完成的扣款/外部操作。

### 数据库灾难恢复

完整数据库恢复是最后手段，必须另行确认：发布后新业务写入可能丢失，外部支付/同步动作不会被数据库恢复撤销。先备份当前故障状态并评估数据对账/补偿，在隔离库恢复并验证后再批准切换；本文不授权 DROP DATABASE、pg_restore --clean 或覆盖生产数据。

## 5. 本地开发库迁移复核工具

`generate-v2-migration-probe.py` 从真实 migration AST 读取 SQL 常量，只生成文件，不连接数据库，已生成 SQL 与本轮 PostgreSQL 通过记录逐字一致（换行归一化）。

```bash
python deploy/backend/generate-v2-migration-probe.py --output <新的本地SQL文件绝对路径>
```

输出存在则拒绝覆盖。检查脚本和 SQL 后，**只通过 fba_dev** 在开发 PostgreSQL 执行；SQL 使用固定的测试 schema、SET LOCAL search_path 和最终 ROLLBACK。必须同时看到 `v2_upgrade_downgrade_and_invalid_data_checks_passed` 与 `fixture_schema_rolled_back=true` 才算通过；异常时停止并确认事务/测试 schema 清理，不能按生产业务 schema 重试。已通过且 SQL 未改时直接继承记录，不再次执行。
