# 云易学试卷采集与导入

功能标识 **`yunyxzx`**。用途：授权接口或本地响应 JSON → 单套试卷导入 V2 → 章节与合集挂载。

**新会话直接发送 [WORKFLOW.md](WORKFLOW.md)**，再补充本轮 sectionId、响应数据、题库名称与目标环境即可。

```text
yunyxzx/
  README.md
  WORKFLOW.md                       # 唯一现行规范
  scripts/
    import_yunyxzx_paper.py         # 主导入器，保留旧业务行为
  runs/                             # 每轮独立日期目录
  archive/
    README.md                       # 风险说明，历史文件不直接执行
    legacy-before-20261101/
      README.md                     # 原说明，部分指导已撤销
      fix_analysis_by_stem.py       # 高风险历史精确匹配修复
      fix_analysis_fuzzy.py         # 高风险历史模糊匹配修复
  archive-migration.json            # 迁移时哈希和缓存清理记录
```

## 本次整理

- 全部源码、旧说明保留，清理3个 Python 字节码缓存；未发现本轮响应或导入结果，不虚构历史任务。
- 主导入器适配仓库/backend定位；文档更正为 `--type`，本地 JSON 分支也必须提供 `--paper-id`。
- 两个修复脚本移到历史区，不作为通用工具；可能批量覆盖题干、所有解析版本和答案，不可直接重放。
- 未抓取接口、未连接数据库。主导入器仍有逐题提交、全库 item_key 去重等限制，使用前必须完整阅读规范。

## 新一轮与清理

在 `runs/YYYYMMDD-任务名/` 下建 README、source、work；先写清范围和授权，先核对响应再预检。
原始响应、最终输入、核验、精确ID与备份信息保留；可重建日志和分片仅在完成并确认可追溯后清理。
