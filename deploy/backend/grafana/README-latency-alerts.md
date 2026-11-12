# 接口延迟告警

`fba_latency_alerts.json` 是 Grafana 官方文件供应配置，部署到
`/etc/grafana/provisioning/alerting/fba_latency_alerts.json`。两条规则独立放在
`fba-latency-rules` 分组，避免接管现有宕机、内存和 5xx 告警。

## 判定方式

- **接口延迟过高**：最近 5 分钟至少 20 次请求，P95 > 5000ms，持续 3 分钟。
- **低流量慢请求**：最近 5 分钟不足 20 次请求，至少一次耗时 > 10000ms，持续 1 分钟。
  使用直方图 `count - bucket{le="10000.0"}` 统计，0.5 门槛容忍 `increase` 的边界外推和浮点误差。
- 两条规则按完整路由模板和请求方法区分。排除 metrics、真正未匹配的路径及原规则排除的微信登录接口。
- 空闲窗口不会因 NaN 告警。恢复只表示告警条件不再满足，不保证接口已经变快；通知文案不再无条件宣称超过阈值。
- 低流量下单次 5–10 秒请求不再作为 P95 告警，仍记录在日志和直方图中，排查时可查看。

## 首次迁移现有 API 规则

必须先上线并验证 `AccessMiddleware` 的路由模板修复，否则排除 `__unmatched__` 会隐藏业务流量。

1. 备份当前规则及 Grafana SQLite 数据库（使用 SQLite backup API，不直接复制运行中的数据库）。
2. 保存其他告警的内容快照，以便迁移后比较。
3. 用有效的组织管理员凭据读取并备份
   `GET /api/v1/provisioning/alert-rules/efn0g1ul3n4zke`，确认来源。
   现网旧规则 `provenance=api`，不能用文件的 `deleteRules` 删除或覆盖，否则 Grafana 供应服务会报错。
4. 使用支持的 API 删除旧规则：`DELETE /api/v1/provisioning/alert-rules/efn0g1ul3n4zke`，
   随即安装上述配置并重启 Grafana；不要直接修改 SQLite 中的来源锁。
5. 确认两条规则创建、供应来源为 `file`、Prometheus 查询及告警评估成功，且其他规则未变。
6. 如为本次迁移创建了临时管理令牌，验证完成后立即撤销；不得留下自动删除规则的供应文件。

以后修改本配置文件后重启 Grafana或通过管理员 API 热加载。文件供应规则无法在网页直接编辑。
数据库备份仅用于灾难恢复；常规回滚优先修改供应文件或使用 Grafana 支持的 API，不能覆盖其他运行期间的配置修改。
