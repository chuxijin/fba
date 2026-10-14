# 计算练习（计算练习 / 速算 / 资料分析）

调用下列命令前必须已成功 `bash scripts/install.sh`。当用户需要生成练习、获取题库教材目录、保存导出 PDF 时使用本页。

> [!NOTE] 生成能力由服务端统一调度，**不依赖本地随机数、计时器或网络缓存**。同一 `seed` 总会返回同一批题目（供错题重画、多人联考场景使用）。

## 题型身份与参数入口

出题前先调用 `calc-catalog` 获取当前后端支持的题型与参数；**不要凭空记忆键名**。如需确认自定义配置合法性，可直接提交 `--params` 校验（FastAPI Schema 会做完整性检查并返回字段级提示）。

```bash
bash scripts/install.sh && node scripts/youanshang.cjs calc-catalog --session-id "当前对话ID"
```

返回 `items: [{key, title, hint, group, type, supports_method_bias, schema, default_params}]`，其中 `schema` 是可直接用于 `calc-generate --params` 的 JSON 键值结构。

## 命令参数

### `calc-generate --kind <kind> [--params <JSON>]`
生成计算练习题单，回显完整 `CalculationSession`（`questions + seed + count + performance_thresholds` 等）。

`kind` 只能是以下四种（对应四类计算能力）：
- `basic`  基础计算，自定义四则/幂运算
- `fill-blank` 资料分析·填空与比较
- `data-practice` 资料分析·实战选择题
- `advanced` 进阶速算（放缩 / 假设分配 / 范围估算 / 特征分数 / 差分法 / 混合）

示例：

```bash
# 基础计算：3 位数 × 个位数，5 道题，固定 seed 保证可复现
node scripts/youanshang.cjs calc-generate --kind basic --session-id "当前对话ID" --params '{"type_key":"custom","count":5,"seed":2026,"custom_config":{"mode":"standard","firstDigits":3,"operators":["×"],"secondMode":"fixed","fixedSecond":7}}'

# 资料分析填空：难度 hard、方法引导 auto、8 道题
node scripts/youanshang.cjs calc-generate --kind fill-blank --session-id "当前对话ID" --params '{"type_key":"growth_amount","difficulty":"hard","method_bias":"auto","count":8}'

# 实战选择题
node scripts/youanshang.cjs calc-generate --kind data-practice --session-id "当前对话ID" --params '{"type_key":"random","difficulty":"normal","method_bias":"auto","count":10,"seed":2026}'

# 进阶速算
node scripts/youanshang.cjs calc-generate --kind advanced --session-id "当前对话ID" --params '{"method":"mixed_speed","mode":"question","count":10,"difficulty":"normal","seed":42}'
```

**注意事项**

- `--params` 必须是**一行** JSON 对象，不能含换行或末尾逗号；整串用单引号包裹以免 shell 转义
- `count` 范围 1-100，默认 10；直接使用用户要求即可（“做 20 道” → `count:20`），不需要备忘提示
- 传 `seed` 可复现同一批题（关键用于重测 / 错题本 / 分享练习），不画重复“最新题单”海报
- 只有 `type_key: 'custom'` 时，必须补充 `custom_config`；否则 schema 校验返回 422 字段错误
- `method_bias` 只对磁盘 catalog 返回的 `supports_method_bias=true` 的题型生效，滥用会直接 422

## `calc-export --kind <kind> [--params <JSON>] [--title "题本标题"]`

**按 seed/参数重生成同一份题单并同步排版为 PDF**（服务端会直接调用既有 render_book 引擎）。仅在用户主动要求纸质 PDF、打印练习、或需要向多人分享的同一份题单文件时调用；**每天建议不超过 N 次（非会员受每日配额限制）**。

输出回显最后包含 `download_path`（相对 URL）与 `title`、`question_count`、`job_id` 等元数据。示例：

```bash
node scripts/youanshang.cjs calc-export --kind basic \
  --title "速算训练卷·第1期" \
  --params '{"type_key":"custom","count":20,"seed":2026,"custom_config":{"mode":"standard","firstDigits":3,"operators":["×","÷"],"secondMode":"range","rangeStart":10,"rangeEnd":99}}'
```

服务端计算导出需遵守会员门禁：HTTP 403 时响应体里回显服务端原始 `msg`（例如“使用公考 AI 助手需要开通会员”），请直接转告用户，不要绕路提交重复请求。

## 错误码含义速查

| code | 责任方建议动作 |
|---|---|
| -1 | INVALID_CONFIG：当前授权 token 的配置已过期（旧版本 skill 缓存）。请用户重新 login（升级本地配置） |
| 403 | 服务端拒绝：会员资格不足或权限不符。把 `msg` 原样告达用户，可引导其到网站开通会员 |
| 422 | 参数校验失败：Schema 校验或排版判断拒绝；输出会带 `msg` 指向缺漏字段（如 `count` 超范围、`custom_config` 缺位数等） |
| -1408 | AUTH_REQUIRED：尚未授权/已过期，先执行 login |

---

提示：生成与导出共用同一批 schema，当需要“只改难度不换题型”进行间隔练习时，仅改动 `--params.difficulty` 即可保持题目结构、教学路径一致。
