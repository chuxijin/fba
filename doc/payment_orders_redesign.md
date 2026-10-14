# 我的订单：页面与用户侧管理

## 已实现

- 五个状态入口：全部、待支付、已支付、退款（含退款中和已退款）、已关闭。
- 服务端关键词、业务类型、支付方式、下单日期过滤及分页；总数为完整筛选结果总数。
- 列表与详情区分支付状态和权益发放状态；不再写死 SVIP，不把未知金额显示为零。
- 删除仅对本人已关闭/已退款的订单生效，写入 `pay_order.user_hidden_at`，不删除交易、不退款、不修改权益。
- 虚拟支付和虎皮椒没有远程关单能力，因此显示“关闭记录”。确认前说明不能阻止原入口后续付款；先核对渠道状态，失败时不伪装关闭成功。
- JSAPI/H5 的取消必须在渠道关单成功后才能写入本地关闭状态。
- 迟到付款或新的退款处理会恢复此前隐藏的记录；重复退款通知不会恢复已退款后由用户主动删除的记录。
- 当前没有从列表继续支付旧订单的实现，不显示虚假的“立即支付”。可核对订单状态、关闭记录后重新选购。

## 2026-10-10：紧凑订单摘要

- 列表改为名称与金额、事件时间与状态、详情/主要操作三组信息，不设固定卡片高度。
- 完整订单号、复制、会员等级及商品类型保留在详情；同类列表不反复显示商品类型，混合类型仍提供区分。
- 普通成功/处理中说明合并进状态，发放失败或权益撤销仍展示“已支付”等重要提示。
- 主操作本身就是查看订单时，不再另设同义的“更多”入口；改用订单尾号辅助区分。
- 同年时间省略年份，跨年保留年份；缺失时间不编造。
- 390px 宽模拟页面测得普通卡片约 137px（上一版约 219～247px），长标题异常样例约 188px；非真机测量。按钮点击高度保持 44px。

## 接口

保留旧的 `GET /api/v1/payment/pay/orders/my` 返回数组格式；新页面使用以下接口：

- `GET /api/v1/payment/pay/orders/my/page`
- `GET /api/v1/payment/pay/orders/my/{order_no}`
- `POST /api/v1/payment/pay/orders/my/{order_no}/refresh`
- `POST /api/v1/payment/pay/orders/my/{order_no}/close`
- `DELETE /api/v1/payment/pay/orders/my/{order_no}`

全部需要登录且由服务端校验订单归属。关闭、删除使用事务与行锁。业务订单的扩展数据不直接下发到客户端，避免泄漏支付身份或渠道参数。

## 数据库与部署

本次没有切换数据库，没有引入 SQLite / aiosqlite，也没有操作开发或生产订单。

新增迁移：`c8d9e0f1a2b3`，前序为 `b7c8d9e0f1a2`。只添加可空列 `pay_order.user_hidden_at`，存量数据无需回填。

**必须先执行数据库迁移，再部署/重启新版后端，最后使用新版小程序。**

在确认环境指向预期 PostgreSQL 数据库后，从仓库目录执行：

```powershell
cd D:\100_Work\101_Program\Proj\fba\backend
uv run --no-sync alembic current
uv run --no-sync alembic heads
# 核对包含哪些尚未执行的迁移，再升级；不要手动覆盖版本号。
uv run --no-sync alembic upgrade head
```

本次没有自动执行迁移。如果前序迁移尚未执行，应先审查它们，不要仅为订单页盲目升级其他模块。

## 验证

后端测试使用现有 PostgreSQL 方言编译真实查询和模拟 DAO/支付渠道，不连接真实业务数据库：

```powershell
uv run --no-sync pytest backend/app/payment/tests -q --disable-warnings
```

小程序目录：

```powershell
node --test tests/payment-orders.test.cjs tests/membership-commerce.test.cjs tests/http.test.cjs
pnpm run type-check
$env:SKIP_OPEN_DEVTOOLS='true'; pnpm run build:mp
```

真机重点：快速切换筛选、底部分页、弹窗滚动与日期选择、关闭确认、删除取消/确认、账户切换、权益处理中与退款中的显示。
真实支付渠道关闭、真实订单删除与生产部署不包含在本地模拟测试内。
