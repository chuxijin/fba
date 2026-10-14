# 授权与账号管理

## 浏览器 OAuth 登录

```bash
node scripts/youanshang.cjs login --session-input "授权" --session-id "1784035443-a1b2c3"
node scripts/youanshang.cjs login --token <授权码> --session-id "1784035443-a1b2c3"
```

以上子命令之前均需成功运行 `bash scripts/install.sh`。默认 login 监听本机、打开浏览器、等待最多 5 分钟；仅最终 `type=result, code=0` 且 `data.authorized=true` 表示保存登录态成功。

`--token` 指的是本次流程的一次性授权码，不是 access_token、API Key 或站内登录 token。CLI 仍持有原先随机生成的 PKCE verifier，并由服务端检验 code 与其绑定；自动回调额外验证 state。手动只提供 code 时，不声称验证了回调 state。

自动登录超时、浏览器未打开或回调端口占用时：

1. 展示失败原因
2. 展示返回的授权链接，不自动重新 login
3. 告知用户在浏览器完成授权后，从跳转后的 URL 复制 `code` 值，直接粘贴回当前对话
4. 得到用户回复后，使用 `login --token` 完成原流程，并恢复最近未完成的操作

待授权状态最长 10 分钟，授权码默认 5 分钟。过期后说明需要重新发起，等待用户要求。不要把授权码重复放入 `--session-input`。

本地网络不支持弹出浏览器时，可用 `login --no-browser`（仍监听回调）或 `login --manual`（只生成授权链接，随后用 --token）。这些不是普通用户需要记忆的步骤，由 Agent 根据失败场景选择。

## 查看账号

`get-user-info` 调用当前账号资料接口，返回昵称、头像与账号标识。以自然语言展示，不能宣称当前没有实现的会员/题库/批改能力。

access_token 自动刷新，刷新写入原子文件并由进程锁互斥。遇到网络不确定时不重放旧 refresh_token。`REFRESH_UNCERTAIN` 时先到授权管理中解绑，或经确认使用卸载脚本清理；不要循环登录。

## 取消授权与退出

用户要求退出、解绑或取消授权时使用 `unauthorize`。它只生成一个 10 分钟有效的确认链接，**不会直接解绑**。

- 展示 `data.revokeUrl` 为可点击链接，原样展示 `data.msg`
- 当前使用普通浏览器网页，不要求夸克 App 或其他不存在的客户端
- 用户需登录发起解绑的同一账号，并确认“解除当前设备授权”
- 只有网页成功提示才表示已解绑；本地 state 文件仍可存在，但其凭据不能再访问服务端
- 链接过期时重新执行安装检查和 unauthorize 获取新链接；若凭据也失效，说明当前设备不能再访问服务端，不改走全设备解绑，不擅自重新授权
- 备用路径“网站 → 应用授权管理”会解绑应用的**全部设备**，应先告知范围区别

`logout` 仅供卸载流程内部使用，撤销当前设备会话；不要求仍有未过期的 access_token，也不会为了注销而刷新一次性 refresh_token。

## 卸载

取得用户二次确认后，执行 `bash scripts/uninstall.sh`，成功后再移除 `youanshang` Skill 文件夹。

若服务不可达，脚本失败并保留凭据，不假装卸载成功。若用户已在网页解绑，服务端可幂等确认设备已退出。

Windows 无可用 Bash 时用等价 `node scripts/uninstall.cjs`。脚本只清理自己的状态文件，不递归删除共享配置目录中的其他文件，不改系统级命令或其他 Agent。

## 本地配置与更新

`runtime.json` 是随包提供的公开部署配置，没有密钥：后端默认 `127.0.0.1:8000`，网站 `127.0.0.1:3000`，公开客户端为已有的 `oac_gongkao_cli_dev`。普通用户不执行 configure。

运行 `bash scripts/install.sh` 会从配置指向的后端获取最新版和完整 ZIP，同步脚本与文档。更新时重新读取 Skill，不要求清除无关记忆。下载只允许 HTTPS 或本机 HTTP，校验包摘要、逐文件摘要与路径白名单，不接收任意外部脚本地址。

安装器首次无绑定状态时输出一次欢迎语；已绑定或已显示过时不重复。显式更新仍使用同一个入口，没有单独的 CLI update。

配置目录默认沿用用户级 `youanshang-skill`（兼容旧 `gongkao-skill`），环境变量 `YOUANSHANG_CONFIG_DIR` 或 `--config-dir` 可隔离测试和不同 Agent。使用隔离目录时，安装脚本与 CLI 必须使用同一设置；更新不迁移现有账号配置。

Node.js 要求 22+。与参考安装器一样检测环境；缺少依赖时明确提示安装，不静默 sudo 或覆盖用户已有 Node。Windows 推荐 Git Bash，不将 WSL 与 Windows 路径混用。
