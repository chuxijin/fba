# youanshang 0.2.0 本地试用与接入交接

更新：2026-10-05。本轮以夸克 Skill 的用户流程为参照，重写了安装、授权兜底、欢迎引导、解绑和卸载入口。以下流程取代旧版 configure/profile/logout 的默认使用方式。

## 用户流程

1. Agent 安装 Skill 到全局 skills 目录
2. 首次及每次业务命令前执行 `bash scripts/install.sh`
3. 脚本检测环境、获取发布配置、下载并校验完整 Skill、同步代码与文档、自检；未绑定首次输出欢迎语，其他情况不刷屏
4. 用户说“授权”，Agent 执行 `login`，打开浏览器并等待用户本人登录与确认
5. 自动回调失败：明确提示用户复制回调 URL 中的 code 并粘贴回对话；Agent 用 `login --token` 继续原流程
6. 用户查询账号：`get-user-info`
7. 用户说“退出/取消授权/解绑”：`unauthorize` 返回设备确认页，用户本人确认后仅当前设备失效，Skill 保留
8. 用户要求卸载：二次确认 → `bash scripts/uninstall.sh` → 成功后由 Agent 删除本 Skill 目录

`logout` 留作卸载内部能力，普通退出不直接调用。`profile`、`configure`、`--callback-url` 保留兼容，但不是新版用户默认入口。

## 与参考 Skill 的一致项与有意差异

| 项目 | youanshang 当前实现 |
| --- | --- |
| 安装入口 | `bash scripts/install.sh` |
| 更新入口 | 同一个安装脚本，同步 CLI、SKILL.md、references，不仅更新命令 |
| 首次欢迎语 | 安装器确定性返回 welcome 行，Agent 原样展示一次 |
| 浏览器授权 | 本机回调、自动打开浏览器、阻塞等待结果 |
| 手动兜底 | `login --token <授权码>`，同一本地待授权状态必须仍存在 |
| 账号查询 | `get-user-info`，目前仅昵称/头像/标识，不编造会员权益 |
| 解绑 | `unauthorize` 返回确认链接，不直接解绑 |
| 卸载 | 先撤销与清理配置，再移除 Skill 文件 |
| 公共参数 | `--session-input`、`--session-id` 兼容；同对话复用随机会话 ID |
| 输出格式 | NDJSON，最终 result code=0 成功、负数失败，msg 为用户提示 |

不机械照搬的部分：

- 本产品没有夸克 App，解绑在自己的普通浏览器网页确认，不生成误导性的 App 扫码提示
- Node.js 需 22+，脚本检测后提示安装；不静默 sudo、覆盖全局 Node 或执行网络 shell 管道
- 撤销失败时保留配置并报错，不继续删除再声称卸载成功
- 接受 session-input 但本地版不上传、落库或回显原始对话；包含秘密的用户输入应省略该参数。遥测需后续独立设计和披露
- 手动 code 仍验证本机 PKCE，不把省略用户操作等同于取消安全检查
- 安装包使用 ZIP 摘要、逐文件摘要、文件白名单与路径校验；不加载外部任意脚本

## 本地环境

公开配置已放在 `skills/youanshang/runtime.json`：

```json
{
  "version": "0.2.0",
  "api_base_url": "http://127.0.0.1:8000/api/v1/openauth",
  "authorize_url": "http://127.0.0.1:3000/openauth/authorize",
  "client_id": "oac_gongkao_cli_dev",
  "redirect_uri": "http://127.0.0.1:17888/callback",
  "scopes": ["profile:read"]
}
```

用户无需配置域名或 client_id。后端和网站必须运行在同一台计算机；`127.0.0.1` 不能用于远端 Agent 或手机访问本机。服务端 client_id 仍为原先已注册的开发标识，不因 Skill 改名而改数据库记录。

网站启动（项目根目录）：

```powershell
pnpm --dir web run dev --host 127.0.0.1 --port 3000
```

后端使用现有开发启动方式运行在 8000。发布配置与安装包接口是后端 `/api/v1/openauth/skill-config` 和 `/skill-package`，从后端直接下载二进制 ZIP，不走网站 JSON BFF。

重新生成完整安装包和发布清单：

```powershell
uv run --no-sync python backend/plugin/openauth/scripts/package_integration.py
```

## 手动试用命令

进入 `skills/youanshang` 后（Windows 推荐 Git Bash）：

```bash
bash scripts/install.sh
node scripts/youanshang.cjs login --session-input "授权" --session-id "1784035443-a1b2c3"

bash scripts/install.sh
node scripts/youanshang.cjs get-user-info --session-input "查看我的账号信息" --session-id "1784035443-a1b2c3"

bash scripts/install.sh
node scripts/youanshang.cjs unauthorize --session-input "退出登录" --session-id "1784035443-a1b2c3"
```

示例会话 ID 仅作格式展示，实际每个新对话生成新的时间戳和随机串。日常用户使用自然语言，不用记忆命令。

浏览器必须由用户本人核对应用、账号与权限，再同意。自动回调成功就不需要粘贴 code。失败时保留本机待授权状态，收到用户 code 后：

```bash
bash scripts/install.sh
node scripts/youanshang.cjs login --token <用户提供的授权码> --session-id "当前对话会话ID"
```

卸载仅在用户二次确认后执行 `bash scripts/uninstall.sh`，成功后再移除整个 youanshang Skill 目录。脚本不会删除 Skill 目录本身，也不会递归删除其他 Agent 配置。

Windows 从 PowerShell 使用 Git 自带 Bash 的场景已验证；若 `bash` 默认指向 WSL，可显式调用 Git Bash，或使用等价 `node scripts/install.cjs` / `node scripts/uninstall.cjs`。不要将 WSL 与 Windows 文件路径混用。

测试隔离可以设置 `YOUANSHANG_CONFIG_DIR`，或每次给安装脚本和 CLI 传同一个 `--config-dir`。配置默认保存在用户级目录，不放在 Skill 内。升级不覆盖已有配置或令牌。

## 设备解绑与安全边界

- `/unauthorize` 必须提供有效开放平台 Bearer，签发 10 分钟有效的确认票据，绑定当前用户与设备会话
- `/device-revoke/preview` 和 `/device-revoke` 需要站内登录，非同一账号不可预览或确认
- `/openauth/revoke?ticket=...` 页面只在用户明确确认后提交，访问链接本身不会解绑
- 设备解绑不改变整个应用的授权关系，其他设备不受影响
- 网站“应用授权管理”仍可解绑整个应用全部设备，必须明确区分范围
- 注销端点仅在降低权限时接受签名有效但已过期的 access token，仍检查 issuer/audience/必需声明；读取、刷新、票据签发依然要求有效授权

目前唯一开放业务为 `profile:read` 的最小账号信息。不开放题库、练习或批改，不继承后台管理员权限。

## 交付与 Git 注意事项

- `artifacts/youanshang-skill.zip`：完整 11 文件 Skill 包
- `artifacts/skill-release.json`：版本、固定下载相对路径、整包和逐文件 SHA-256
- `artifacts/openauth-web-integration.zip`：三个网站页面、授权辅助代码和本交接文档
- `artifacts/manifest.json`：交付包内容和摘要

根 `.gitignore` 排除了整个 `web/`，因此网站改动不会出现在普通 git status 中。本轮不改变此策略，已提供源码包防止交接遗漏；合并网站仓库时审查 analytics 插件等现有文件，不盲目覆盖。

## 验证结果与仍未完成的验收

- 后端 55 项隔离测试通过，包括真实 Node CLI → FastAPI 路由的 `login --token`、查询、刷新、退出协议联调
- Node 18 项测试通过，包括完整包更新、欢迎语去重、登录态保留、篡改/路径越界拒绝、安装/卸载失败边界、设备解绑链接
- Windows Git Bash 已对真实本地后端运行：下载修复旧文档 → 再次检查不下载 → 未授权查询返回 -1408 → 卸载清理无账号测试配置
- 设备解绑页面未登录态已在浏览器检查，页面显示仅本人确认后解绑，控制台没有错误；未自动登录或提交确认
- OpenAuth 专用 TypeScript 检查退出码 0，保留现有 vue-router/volar 兼容提示；全站已有业务类型错误未处理
- 后端 Ruff 和 Skill 元数据校验通过；已用独立离线使用场景核对 Agent 不把生成链接误认为解绑成功、不为单设备退出调用全设备解绑

测试没有借用真实用户登录态，没有索取账号密码，没有自动替用户同意。真人账号的浏览器授权和解绑还需要用户本人验收。生产环境、域名、历史 Alembic 记录仍未修改，也未提交或推送 Git。

正式部署时：先在目标环境注册客户端和回调，修改 runtime.json 的公开地址与 client_id，再重新打包发布；不是只改域名字符串就等同部署完成。已有用户配置不自动跨服务迁移，需先退出或使用新的隔离配置目录。
