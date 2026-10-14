# 虎皮椒（xunhupay）支付渠道接入说明

> 适用代码：`backend/common/payment/providers/hupijiao.py`、`backend/app/payment/**`、`backend/core/conf.py`
> 协议依据：虎皮椒官方文档《发起付款接口》《订单查询接口》《订单退款接口》及官方分发的 PHP / WooCommerce / Laravel SDK 源码。

## 1. 背景与改动范围

在原有微信虚拟支付（`virtual`）与微信 JSAPI/H5 之外，新增 `hupijiao` 渠道，并让**订阅套餐**同时支持两种收款方式。
渠道通过支付方式（`pay_type`）路由，未改动既有微信渠道的行为。

涉及文件：

| 文件 | 作用 |
| --- | --- |
| `backend/common/payment/providers/hupijiao.py` | 新增：虎皮椒 API 1.1 适配器 |
| `backend/common/payment/dispatcher.py` | 注册 `hupijiao`；回调解密支持指定渠道 |
| `backend/core/conf.py` | 新增配置项；回调地址加入免鉴权白名单 |
| `backend/app/payment/schema/pay.py` | `PayType` 增加 `hupijiao`；预下单参数按渠道校验 |
| `backend/app/payment/service/pay_service.py` | 渠道校验、行级锁、退款状态机 |
| `backend/app/payment/service/pay_order_service.py` | 订阅预下单按渠道组装参数 |
| `backend/app/payment/api/v1/pay.py` | 新增虎皮椒回调路由 |
| `backend/.env.example` | 配置样例 |

## 2. 配置项

```dotenv
# [ App ] 虎皮椒支付（APPID 对应已开通的收款渠道）
HUPIJIAO_APPID=''
HUPIJIAO_APPSECRET=''
# 网关根地址，不包含 /payment/do.html
HUPIJIAO_API_BASE_URL='https://api.xunhupay.com'
# 公网 HTTPS 回调，例如 https://api.example.com/api/v1/payment/pay/hupijiao/notify
HUPIJIAO_NOTIFY_URL=''
# 可选：移动端付款完成后的网页跳转地址
HUPIJIAO_RETURN_URL=''
```

| 配置 | 必填 | 说明 |
| --- | --- | --- |
| `HUPIJIAO_APPID` | 是 | 应用 ID，**决定实际收款渠道**（微信/支付宝由后台开通的 APPID 决定） |
| `HUPIJIAO_APPSECRET` | 是 | 密钥，仅用于签名；`settings` 中已设 `repr=False` 避免日志泄漏 |
| `HUPIJIAO_API_BASE_URL` | 是 | 网关根地址，须为 HTTPS；官方备用网关为 `https://api.dpweixin.com` |
| `HUPIJIAO_NOTIFY_URL` | 是 | 支付与退款回调地址，HTTPS、**不超过 128 字节** |
| `HUPIJIAO_RETURN_URL` | 否 | 付款完成后浏览器跳转地址；留空则不下发该参数 |

凭证在**使用时**校验，因此未开通虎皮椒时留空不会导致服务启动失败，仅在下单时报“虎皮椒 APPID 或 APPSECRET 未配置”。

回调地址已加入 `Settings.PUBLIC_URLS` 免鉴权白名单：`/api/v1/payment/pay/hupijiao/notify`。

## 3. 接口说明

完整路径前缀为 `/api/v1`，支付模块前缀为 `/payment`。

### 3.1 订阅套餐预下单

`POST /api/v1/payment/pay/subscription/prepay`（需登录）

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `template_code` | string(64) | 订阅模板编码 |
| `pay_type` | `virtual` \| `hupijiao` | 默认 `virtual`（保持原有行为） |
| `wx_code` | string \| null | **虚拟支付必传**；虎皮椒无需 |
| `env` | `0` \| `1` | 虚拟支付环境；虎皮椒仅支持 `0`，传 `1` 直接校验失败 |

返回 `{order_no, transaction_no, pay_params}`。`pay_params` 由渠道决定：

- `virtual`：微信小程序拉起虚拟支付所需参数
- `hupijiao`：`{"url_qrcode": "二维码图片地址", "url": "移动端支付链接", "expires_in": 300}`

前端应区分处理：PC 端展示 `url_qrcode`，移动端跳转 `url`。**官方说明两者不可先用二维码再跳链接。**

### 3.2 确认订阅支付状态

`POST /api/v1/payment/pay/subscription/confirm`（需登录）

参数 `order_no`、可选 `wx_code`（仅虚拟支付在缺失 openid 时需要）。未支付时会主动向渠道查单。

### 3.3 虎皮椒支付及退款回调

`POST /api/v1/payment/pay/hupijiao/notify`（免鉴权）

- 请求：`application/x-www-form-urlencoded` 表单
- 应答：成功返回纯文本 `success`；失败返回 `fail` 且状态码 500，以触发渠道重试
- **只使用虎皮椒验签**，不会回退到其他渠道解析；业务事务提交成功后才返回 `success`
- 支付（`OD`）与退款（`CD`/`RD`/`UD`）共用该地址

> 该路由使用 `db.begin()` 显式事务，异常时回滚并返回 `fail`，避免“未落库却告知渠道已收到”。

### 3.4 微信回调（原有，行为不变）

`POST /api/v1/payment/pay/notify`、`POST /api/v1/payment/pay/refund-notify`。
已改为 `CurrentSession` + 显式事务，并支持 XML / XPay JSON / 默认三种应答格式。

## 4. 支付流程

```
小程序/前端                后端                        虎皮椒
    |  prepay(pay_type=hupijiao)  |                          |
    |--------------------------->|  创建支付记录(pending)     |
    |                            |  POST /payment/do.html -->|
    |                            |  验签 + 校验 errcode       |
    |<-- url_qrcode / url -------|                           |
    |  用户扫码支付                |                          |
    |                            |<-- POST notify(form) -----|
    |                            |  验签 → 归一化 → 行锁      |
    |                            |  标记 paid + 业务发放      |
    |                            |--- success -------------->|
```

## 5. 状态机、幂等与并发

`pay_transaction.status`：`pending → paid → refund_pending → refunded`，或 `pending → closed`。
`pay_order.fulfill_status`：`pending → fulfilled`，退款后为 `revoked`。

- **行级锁**：确认支付、退款结果处理均以 `SELECT ... FOR UPDATE` + `populate_existing=True` 锁定支付记录与业务订单，避免回调与主动确认并发重复发放。
- **渠道绑定校验**：`_validate_channel_result` 校验“通知渠道 == 订单渠道”“订单号一致”“金额一致”；虎皮椒要求金额字段必须存在且为精确到分的正整数。
- **幂等**：重复回调不会重复发放（已 `fulfilled` 时跳过通知）；退款完成后的延迟支付通知被忽略。
- **金额精度**：`_yuan_to_fen` 拒绝非正数、非有限值和非精确到分的金额，避免精度丢失后按错误金额收款。
- **退款状态机**：`SUCCESS` → 记录与订单置 `refunded` 并通知撤销；`PROCESSING` → `refund_pending`；`FAILED` → 回退 `paid`。

## 6. 协议核对结论

签名算法（官方文档与官方 PHP / WooCommerce / Laravel SDK 实现一致）：

```php
function generate_xh_hash(array $datas, $hashkey){
  ksort($datas); reset($datas);
  $arg = '';
  foreach ($datas as $key=>$val){
    if($key=='hash' || is_null($val) || $val===''){ continue; }
    if($arg){ $arg .= '&'; }
    $arg .= "$key=$val";
  }
  return md5($arg.$hashkey);
}
```

来源：[pay.html](https://www.xunhupay.com/doc/api/pay.html)、[search.html](https://www.xunhupay.com/doc/api/search.html)、[refund.html](https://www.xunhupay.com/doc/api/refund.html)

要点：

1. **只跳过 `null` 与空字符串**；数字 `0`、字符串 `'0'`、`false` 都算“非空”，必须参与签名。因此实现对 `errcode: 0` 这类字段必须照常参与，不能写成“跳过所有假值”。
2. 非空参数按参数名 ASCII 升序，拼成 `k=v&k=v`（末尾无 `&`），**值不做 URL 编码**，末尾直接拼接 APPSECRET（无分隔符），MD5 取 32 位小写。
3. 下单与退款响应均含 `hash`，且官方 demo 对**整个响应体**（含 `errcode`/`errmsg`）重算校验，因此可对响应验签。
4. `trade_order_id`：`string(32)`，**只能是数字、大小写字母及 `_ - *`**。
5. `total_fee`：**单位是元**，`decimal(18,2)`；本实现下单时格式化为两位小数。
6. `notify_url` / `return_url`：`string(128)`。
7. 回调字段：`trade_order_id`、`total_fee`、`transaction_id`、`open_order_id`、`order_title`、`status`、`appid`、`time`、`nonce_str`、`hash`（`plugins`/`attach` 传入才回传）。
8. 二维码**有效期 5 分钟**；**官方没有主动关单接口**，故 `close()` 为本地空操作。
9. 退款请求**不含任何金额参数**，因此只能整单全额退款；本实现要求 `refund_fee == total_fee`。

### 6.1 两套 status 语义不同（易踩坑）

| 语境 | 取值 |
| --- | --- |
| 查单 `data.status` | `OD` 支付成功、`WP` 待支付、`CD` **已取消** |
| 回调 / 退款响应 | `OD` 已支付、`CD` **已退款**、`RD` 退款中、`UD` 退款失败 |

`CD` 在两处含义完全相反。实现分别映射：查单 `CD → CLOSED`，回调 `CD → refund_status=SUCCESS`，并有回归测试固定该差异。

## 7. 相对协议的有意加强

| 项 | 协议要求 | 本实现 | 原因 |
| --- | --- | --- | --- |
| 回调/跳转地址 | HTTP 或 HTTPS，须带域名 | 仅 HTTPS | 支付回调携带订单状态，强制 TLS 降低被伪造与窃听风险 |
| `title` | ≤127 字符或 42 汉字，禁止 `%` 与表情 | 按 UTF-8 截断至 127 字节并过滤 `%` 与非平面字符 | 127 字节 ≈ 42 汉字，同时满足两种口径 |
| 下单报文 | 文档写 JSON，部分官方 demo 用表单 | JSON | 以官方文档口径为准 |
| 查单响应验签 | 官方未给出嵌套 `data` 的拼串规则，官方 demo 从不验签 | 不验签，仅 HTTPS 直连且禁止重定向 | 无法确定覆盖范围时不做错误假设 |
| 退款响应验签 | 官方仅在成功分支验签 | 一律验签 | 更严格，失败响应同样要求签名有效 |

## 8. 上线前需实测确认的项

以下项在官方文档/源码中**无权威明文**或存在来源冲突，已按较保守方式实现，但需在真实环境验证：

1. **`do.html` 响应是平面字段还是嵌套 `data`（最高优先级）**：官方文档 [pay.html](https://www.xunhupay.com/doc/api/pay.html) 的响应表为平面字段（`oderid` / `url_qrcode` / `url` / `errcode` / `errmsg` / `hash`），示例 JSON 亦是平面；而官网 `plugin.html` 挂出的「虎皮椒支付 ai 对接 skill」包（含 `SKILL.md` / `reference.md` / `examples/xunhupay_demo.py`）声称成功响应嵌套在 `data` 内。本实现按官方文档读取**平面**字段。若真实网关实为嵌套，会在验签阶段即报「虎皮椒响应签名验证失败」——因为 `data` 是对象，无法按已文档化的拼串规则参与签名。**下单实测时须首先确认本项。**
2. **回调中退款字段名**：退款接口响应使用 `refund_status`，而回调示例仅体现 `status`。若渠道在退款回调中只传 `refund_status` 而不传 `status`，当前归一化会因缺字段而拒绝。上线前应实测一笔真实退款回调。
3. **退款回调是否携带 `total_fee`**：实现对所有回调都要求金额可解析。若退款通知不含金额，需放宽该校验。
4. **查单 / 退款报文格式**：官方文档与 PHP 官方 SDK 使用表单提交，而上述 ai 对接包声称三个接口统一用 JSON。本实现为 `do.html` 用 JSON、`query.html` / `refund.html` 用表单。若真实网关只接受其中一种，需相应调整。
5. **`total_fee` 金额上下限**：官方未给出明确区间。
6. **失败响应的 `hash`**：文档示例中成功与失败响应使用了同一个 hash 占位值。若真实失败响应签名无效，当前会报“响应签名验证失败”而非原始 `errmsg`，定位体验略差。

> ⚠️ 关于官网 `plugin.html` 的「虎皮椒支付 ai 对接 skill / 下载源码」：它是一个 **AI Agent Skill 包**（`README.md` 自称“Skills 仓库”，含 `SKILL.md` 与多语言 demo），**不是官方语言 SDK**。其**签名算法与官方文档完全一致**（过滤空字符串/`None`、排除 `hash`、ASCII 升序、`k=v&…`、末尾拼 secret、MD5 小写），可作为签名的独立佐证；但它在**下单响应结构**（声称嵌套 `data`）与**请求报文格式**（声称全部 JSON）两点上与官方文档冲突，且其示例**不校验响应签名**、用 `==` 而非恒定时间比较校验回调签名，并遗漏 `refund_status=UD`。**请勿以该包作为对接依据，本实现以官方 API 文档为准。**

## 9. 网页端接入（web/ Nuxt 站点）

网页端通过 BFF 代理直连后端：浏览器请求 `/api/**` → `web/server/api/[...].ts` → `${NUXT_API_BASE_URL}`（默认 `http://127.0.0.1:8000/api/v1`），并透传 `Authorization`。

| 文件 | 作用 |
| --- | --- |
| `web/app/types/payment.ts` | 套餐 / 预下单 / 支付确认 / 我的权益类型 |
| `web/app/api/payment.ts` | 套餐列表、虎皮椒预下单、支付确认、权益汇总四支接口 |
| `web/app/pages/pricing.vue` | 会员定价页（路由 `/pricing`） |
| `web/app/components/pricing/PayDialog.vue` | 支付弹窗：PC 展示二维码、移动端跳转、倒计时、轮询确认 |
| `web/app/components/profile/VipGlowCard.vue` | 改为接收真实会员数据，并加入 `/pricing` 入口 |
| `web/app/pages/profile/index.vue` | 拉取 `/access/my/summary` 并映射为卡片数据 |
| `web/app/components/layout/SiteHeader.vue` | 导航新增「会员」入口 |

使用的后端接口（**均需登录**）：

| 用途 | 接口 |
| --- | --- |
| 套餐列表 | `GET /access/templates?status=active&page=1&size=100` |
| 预下单 | `POST /payment/pay/subscription/prepay`（`pay_type=hupijiao`） |
| 支付确认 | `POST /payment/pay/subscription/confirm` |
| 权益汇总 | `GET /access/my/summary` |

支付流程：

1. 选择套餐 → 预下单，得到 `{order_no, pay_params: {url_qrcode, url, expires_in}}`
2. PC 端展示 `url_qrcode` 二维码；移动端跳转 `url` 打开 H5 收银台
3. 前端每 3 秒调用确认接口（后端会主动向渠道查单），支付成功后权益自动发放
4. 待支付订单号写入 `localStorage`，移动端支付返回后自动确认一次
5. 二维码 5 分钟过期后提示重新下单

注意事项：

- 套餐价格字段 `price_cents` 单位是**分**；支付订单的 `amount` 是**元**字符串，两者不要混用
- `/access/templates` 需要登录，未登录时页面引导唤起站内登录弹窗（`auth:require-login` 事件）
- 可售判定（`status=active` 且 `price_cents>0` 且当前时间在上架时间段内）在前端同步实现，否则点击后才收到 403
- 会员状态**没有** `vip_level` 字段，需从 `membership.is_member` / `tier_name` / `valid_to` 读取（`valid_to` 为 `null` 表示永久）

> ⚠️ 根仓库 `.gitignore` 中「Flutter / Mobile」段落的 `web/` 规则会把**整个 Nuxt 站点**排除在版本管理之外，而 `web/` 目录本身没有独立 git 仓库（`mini/`、`frontend/` 有）。该规则疑似 Flutter 模板遗留（仓库内无 `pubspec.yaml`/`lib`），上线前需要处理。

## 10. 测试

```bash
# 支付模块测试（渠道适配、调度、渠道规则、回调流程、原有流程）
uv run pytest backend/app/payment/tests -q
```

覆盖范围（67 个用例）：

- `test_hupijiao_provider.py`：签名规则（含 `0` 参与、不做 URL 编码）、下单/查单/退款报文与响应、回调验签与归一化、金额精度、订单号限制
- `test_pay_dispatcher.py`：渠道注册、未指定渠道保留遍历、**指定渠道绝不回退**
- `test_pay_channel_rules.py`：金额换算、渠道/订单号/金额校验、订阅参数按渠道校验
- `test_pay_callback_flow.py`：支付成功落库与发放、重复回调幂等、订单缺失触发重试、金额不符拒绝、退款三态流转、退款后延迟支付忽略
- `test_pay_service.py`：原有超时关单流程（已适配新增的 `for_update` 参数）

## 11. 上线检查清单

- [ ] 虎皮椒后台配置的异步通知地址与 `HUPIJIAO_NOTIFY_URL` 完全一致，且为 HTTPS、≤128 字节
- [ ] `HUPIJIAO_APPID` 对应已开通的收款渠道（微信 / 支付宝）
- [ ] `HUPIJIAO_APPSECRET` 未写入日志、未提交到仓库
- [ ] 网关地址可访问（正式 `api.xunhupay.com`，备用 `api.dpweixin.com`）
- [ ] 实测一笔真实支付：下单 → 扫码 → 回调 → 权益发放
- [ ] 实测一笔真实退款：确认整单全额退款与权益撤销
- [ ] 确认回调重试期间不会重复发放权益
- [ ] 网页端 `/pricing` 能展示套餐并完成一笔真实支付，个人中心到期时间同步更新
- [ ] 根 `.gitignore` 中误加的 `web/` 规则已处理，网页端代码纳入版本管理
- [ ] 管理后台已配置可购买的订阅套餐（`status=active` 且 `price_cents>0`），否则定价页为空
