---
name: youanshang
description: youanshang 官方 Skill，用于绑定公考账号、查看账号信息与授权状态、解除设备授权、安装更新和卸载；已开放计算练习出题与题库检索（目录/题目/详情）。当用户提及 youanshang 并需要账号操作、身份验证、出计算练习或查题时使用。
---

# youanshang 官方 Skill

通过本地命令行工具调用 youanshang 开放平台。安装、欢迎引导、浏览器授权、手动授权码、解绑与卸载使用统一流程。

## 安装与命令前检查

首次使用及**每次调用 CLI 子命令之前**，先运行：

```bash
bash scripts/install.sh
```

脚本检查 Windows/macOS/Linux 与 Node.js 22+，请求发布配置，必要时下载并校验完整 Skill，同步 CLI、SKILL.md 和 references，再自检。失败时停止，不继续调用业务命令，不循环重试。

所有路径相对于本 Skill 目录。跨目录调用使用脚本绝对路径。Windows 使用 Git Bash；只有系统不提供可用 Bash 时，改用等价入口 `node scripts/install.cjs`，不要把 WSL 的路径与 Windows Node 混用。

安装到 Agent 的全局 skills 目录，避免项目清理导致丢失。当前包已内置本地服务配置，不需要用户提供域名、client_id 或执行 configure。开发服务必须运行在同一台计算机上；不能把此包当成生产版。

### 更新

用户要求“更新/升级 Skill”时，执行同一个 `bash scripts/install.sh`。不要只更新 CLI；下载后重新读取 SKILL.md。常规检查在本地文件完整且版本一致时跳过覆盖，不改用户登录态。

### 首次安装／未绑定欢迎语

安装器出现 `type=welcome` 时，将其 `msg` 原样展示一次。若没有该行，不重复欢迎语。固定文案为：

```text
👋 你好！绑定 youanshang 账号后，可以直接在对话中使用已开放的账号能力。

绑定后目前可以这样使用：
●「我登录的是哪个账号？」
●「查看我的账号信息」
●「给我出十道三位数乘法练习」
●「查一下 2026 年时政题库里的题目」
●「解除当前设备的授权」

👆 请回复「授权」绑定 youanshang，绑定后即可使用以上功能。
```

仅安装/更新时，输出欢迎语后等待用户，不擅自发起绑定。用户已明确要求需要账号的操作时，按未授权流程继续。

## 调用方式与公共参数

```bash
node scripts/youanshang.cjs <command> [options] --session-input "用户原始提问" --session-id "1784035443-a1b2c3"
```

- `--session-input`、`--session-id` 是子命令参数，不是独立命令
- 首次调用时生成 `{Unix秒时间戳}-{6位随机字母数字}` 会话 ID，同一对话复用；不使用语义化名称
- 参数以当前用户原始提问为准，不摘要；无法获得原文时可省略。原文含密码、验证码、授权码或令牌时省略 `--session-input`，避免二次复制秘密
- 通过安全的参数传递方式调用，不能将用户文本拼成可执行 shell 语句
- 本地版只兼容接收这两个参数，**不上传、记录或回显用户原始提问**；启用遥测是独立产品决策，不把参数兼容当作用户同意采集

标准输出为 NDJSON；最终 `type=result`、`code=0` 表示本命令执行成功，负数为失败。`unauthorize` 的成功仅表示生成确认链接，不能据此宣称解绑完成。`reason` 供诊断，用户优先看到 `msg`。辅助 `type=authorization` 不是最终登录成功。

## 授权与未授权处理

用户说“授权/登录/绑定”时，先安装检查，再执行 `login`，展示可点击的授权链接，等待用户本人在浏览器登录并确认。命令阻塞等待回调，结束后检查最终结果。

遇到 `code=-1408` 或 `reason=AUTH_REQUIRED`：先展示未授权说明，停止重复原命令，引导 `login`。登录成功后继续用户尚未完成的原任务一次；取消或再次失败则停止。

自动登录失败或超时：先展示原因，再给出返回的授权链接，并明确说明“完成授权后，从跳转后的地址复制 code 参数的值，直接粘贴回当前对话发给我”。等用户回复后执行 `login --token <授权码>`。不要自动再次启动 login，避免覆盖待授权会话。

手动模式仍要求同一设备保存的待授权状态与 PKCE；不能接受无前置登录流程的授权码。详情见 [授权与账号管理](references/auth.md)。

### 登录成功后的引导

用户主动要求登录、首次绑定时，原样输出：

```text
授权登录成功！现在你可以：
● 查看当前绑定的账号信息
● 在对话中查询授权状态
● 生成计算练习并导出 PDF
● 检索公开题库（目录 / 题目 / 答案解析）
● 随时解除当前设备的授权
```

若本次登录仅为恢复原任务的自动授权流程，则直接继续原任务，不重复能力介绍。

## 功能域

- **计算练习（题库与速算）**：
  - `calc-catalog` 查询当前支持的题型、方法参数 schema；生成/导出前必须查一次
  - `calc-generate --kind basic|fill-blank|data-practice|advanced [--params JSON]` 生成题单；server 校验错误直接输出 422 字段原因
  - `calc-export --kind KIND [--params JSON] [--title "题本标题"]` 按相同 seed/参数重生成辅导出 PDF；遇 HTTP 403 直接沿服务端原文案引导用户开通会员，不自动兜底
- **题库检索（只读）**：
  - `qbank-banks [--category-id ID] [--bank-kind practice|paper|mock] [--keyword 词]` 已发布题库目录
  - `qbank-search --bank-id ID [--question-type 题型] [--keyword 词]` 题目列表（不含答案解析）
  - `qbank-detail --id 题目ID` 题目详情（含选项、答案、解析）；详见 [题库检索](references/qbank.md)
- **题库检索（只读）**：
  - `qbank-banks [--category-id ID] [--bank-kind practice|paper|mock] [--keyword 词]` 已发布题库目录
  - `qbank-search [--bank-id ID] [--question-type 题型] [--keyword 词]` 检索题目列表（不含答案解析）
  - `qbank-detail --id 题目ID` 题目详情（含选项、答案、解析、知识点）。详情见 [题库检索](references/qbank.md)
- **账号资料**：`get-user-info`（昵称、头像与会员态），`check`
- **取消授权／解绑／退出登录**：`unauthorize`，展示 `data.revokeUrl` 为可点击链接及 `data.msg`，等待用户本人在网页确认。拿到链接不等于已经解绑
- **备用解绑路径**：网站 → 应用授权管理；此入口解绑整个应用的全部设备，必须与上面的“仅当前设备”区分

普通解绑不要调用 logout。`logout` 是卸载流程的内部命令，不是用户主动退出的默认入口。

## 卸载／删除

先向用户说明并取得二次确认：解除本设备授权、清除当前本地配置、移除 Skill 文件；账号和业务数据不删除。

1. 执行 `bash scripts/uninstall.sh`，撤销本机授权并清除当前配置
2. 仅脚本成功后，删除本 Skill 所在的 `youanshang` 目录；不要删除整个 skills 目录

脚本失败时保留配置与 Skill，明确告知尚未确认撤销。不能跳过撤销直接删除文件，也不能将“仅清本地”说成已解除服务端授权。

## 隐私与边界

不读取、展示或上传本地 `state.json`；使用 status 诊断。不向用户索取站内密码，不把验证码、token、verifier 写到总结中。用户主动提供的一次性授权码只用于换票，不复述。

用户本人确认授权；Agent 不代点“同意”。不声称当前未接入的做题、批改、文件管理功能可用。
