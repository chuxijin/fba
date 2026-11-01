# 考研兔题库采集与导入

功能标识 **`kaoyantu`**。用途：授权抓包 → V2 Excel → 题库、章节、材料与合集挂载。

**新会话直接发送 [WORKFLOW.md](WORKFLOW.md)**，再补充本轮数据、题库名称和目标环境即可。它与“题库解析精编与发布”是不同工作。

```text
kaoyantu/
  README.md
  WORKFLOW.md                       # 唯一现行规范
  scripts/
    extract_kaoyantu_from_burp.py    # 离线提取，必须指定输出路径
    import_to_v2.py                 # 旧导入器，先审核限制再预检/导入
  runs/                             # 每轮独立日期目录
  archive/
    README.md                       # 历史风险与路径说明
    legacy-before-20261101/         # 旧说明、绑定旧请求的HTTP导出器
  archive-migration.json            # 迁移时文件哈希和缓存清理记录
```

## 本次整理

- 保留全部源码与旧说明，清理3个 Python 字节码缓存；未发现本轮源数据或导入成品，不虚构历史执行记录。
- 现行导入器适配仓库/backend定位；离线提取器不再默认输出到 backend/scripts/outputs，必须指定 `--output`。
- 旧 HTTP 导出器依赖固定题库、抓包签名和请求参数，作为历史参考保存，不是通用采集入口，不对外发布。
- 未执行源站抓取或数据库操作。只读预检不等于事务预演，旧导入器仍有逐题提交、全库去重等限制。

## 新一轮与清理

在 `runs/YYYYMMDD-任务名/` 下建 README、source、work，填写真实状态。数据检查、预检、正式导入、恢复规则见完整规范。
源快照、最终Excel、核验、精确ID和备份信息长期保留；任务完成且可追溯后仅清理 work 中可重建文件。
