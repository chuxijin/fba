# 网站统计

自托管多站点访问统计插件，提供匿名 PV/UV、会话、事件、来源、设备、地域、热力图、Web Vitals、公开计数器和 rrweb 会话回放数据能力

## 插件类型

- 应用级插件

## 配置说明

在 `backend/.env` 中添加以下内容：

```env
WEB_ANALYTICS_HASH_SALT='replace-with-a-stable-random-secret'
```

插件目录下 `plugin.toml` 的 `[settings]` 中包含以下内容：

```toml
[settings]
WEB_ANALYTICS_HASH_SALT = 'change-me-before-production'
WEB_ANALYTICS_EVENT_RETENTION_DAYS = 180
WEB_ANALYTICS_REPLAY_RETENTION_DAYS = 30
WEB_ANALYTICS_MAX_BATCH_SIZE = 50
WEB_ANALYTICS_MAX_REPLAY_BYTES = 524288
```

## 配置项说明

- `WEB_ANALYTICS_HASH_SALT`：生成不可逆访客和 IP 哈希
- `WEB_ANALYTICS_EVENT_RETENTION_DAYS`：默认原始事件保留周期
- `WEB_ANALYTICS_REPLAY_RETENTION_DAYS`：默认会话回放保留周期
- `WEB_ANALYTICS_MAX_BATCH_SIZE`：单次事件上报数量上限
- `WEB_ANALYTICS_MAX_REPLAY_BYTES`：单个回放分片大小上限

## 使用方式

1. 安装并启用插件后创建统计站点，将生成的接入脚本嵌入允许的站点域名
2. 使用管理端授权接口查看总览、趋势、热力图和会话回放数据
3. 需要会话回放时加载 rrweb 并调用统计脚本提供的回放启动方法
4. 使用项目调度系统定期调用维护操作，生成每日汇总并清理超过保留期的明细

## 卸载说明

- 卸载插件并清理统计数据表、站点接入脚本和相关环境变量

## 联系方式

- 作者：`gongkao`
- 反馈方式：提交 Issue 或 PR
