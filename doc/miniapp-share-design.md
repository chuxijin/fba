# 小程序分享内容设计（标题与封面）

- 状态：**待评审**
- 日期：2026-10-19
- 影响范围：`mini` 小程序；后端复用现有 CMS 运营位，**不改表结构**
- 相关代码：`backend/app/cms/`、`mini/src/composables/`、`mini/src/api/endpoints/system.ts`、`mini/src/App.vue`

---

## 1. 一句话结论

分享内容 = **实体数据**（题库名/封面/题量）+ **运营文案**（邀请语/品牌图），
用「一个前端统一 resolver + 三层数据源」实现，配置侧**复用现有 CMS 运营位**（新增 `slot_type='share'`），
不上新表、不上新接口。

---

## 2. 背景与现状

### 2.1 现状：全项目只有 3 个页面真的能转发

微信规范要求页面自身声明 `onShareAppMessage`，未声明则右上角「转发」为灰色不可点。当前实现：

| 页面 | 标题来源 | 封面来源 | 分享路径 |
| --- | --- | --- | --- |
| `pkg/mine/share-gift` | `sys_config(INVITE)` 文案池**随机**一条 | 文案池配图 | `/pages/practice/index?invite_code=xxx` |
| `pkg/mine/group-buy` | `${people} 人一起拼「${template_name}」，成团后开通` | **无** → 微信页面截图 | `/pkg/mine/group-buy/index?code=xxx` |
| `pkg/resource/detail` | 资料名 | `images[0]` | `/pkg/resource/detail/index?id=xxx` |

其余页面（含**题库详情、知识点详情、刷题首页**）**完全没有转发入口**。

### 2.2 现有的"统一分享配置"只有一个文案池

```
GET /api/v1/invite/codes/share-config  →  [{ title, image }]
```

实现：`backend/app/invite/api/v1/invite_code.py:54-86`
读取 `sys_config` 中 `type=INVITE && is_frontend=true` 的行，每行 `value` 为 `{title, image}` JSON。
无数据时兜底一条 `送你一份 VIP 学习订阅`。

特点：**与实体无关**，只是一个文案池，仅被「分享有礼」一个页面消费。

### 2.3 题库已有封面字段，但前端从未消费

- `QbBankRevision.cover_url` / `cover_asset_id`：`backend/app/question_bank_v2/model/bank.py:127-133`
- 接口已透出：`GetBankRevisionDetail.cover_url`
- 小程序 `pkg/practice/bank-detail/index.vue:42` 已接收并赋值（`:1323`），**但模板中从未渲染**

即：题库封面这条数据链路是通的，但"最后一公里"没接。

### 2.4 由此归纳 4 个问题

1. **覆盖面**：100+ 页面里只有 3 个能转发，核心的题库/知识点无法被分享。
2. **视觉**：3 个可分享页面中 2 个没有配图，走微信默认"页面截图"，会把按钮/骨架屏截进卡片。
3. **口径**：标题一处用实体名、一处用运营文案、一处随机，无统一规范。
4. **可运营性**：除邀请文案池外，文案和封面无处可配，改一句话要发版；也没有分享数据。

---

## 3. 平台约束（微信官方规范）

以下 4 条直接决定架构形态：

| # | 约束 | 对设计的影响 |
| --- | --- | --- |
| C1 | 必须页面级声明 `onShareAppMessage` 才点亮转发入口，**没有全局默认分享** | 每个要分享的页面都要挂一层 → 必须抽 `useShare` composable，不能指望全局配置 |
| C2 | `imageUrl` 推荐 **5:4**（建议 500×400），支持 https 网络图或本地临时文件 | 题库封面大概率非 5:4，直接传会被居中裁切；配图必须按 5:4 生产或合成 |
| C3 | `onShareTimeline`（朋友圈）**只能带 query，不能带 path**；打开为"单页模式"（无 tabBar、登录态不持久、部分 API 不可用） | 仅纯展示页开放朋友圈；业务页默认关闭 |
| C4 | **拿不到"分享成功"事件** | 分享量只能按"点击转发"计；归因必须靠落地页 query 参数 |

补充说明：

- 分享 `path` 必须写**完整分包路径**（`/pkg/practice/bank-detail/index?id=1`），不能写相对路径。
- 分享到 tabBar 页面可以带 query 正常打开，但页面内再次 `switchTab` 会丢失 query。
- 「群分享 + `withShareTicket`」可拿到 `shareTicket` 并通过 `wx.getShareInfo` 校验是否来自群，但仅限群聊且需后端解密，本期不做。

---

## 4. 目标与非目标

### 目标

- **G1** 让核心页面（题库详情、知识点详情、刷题首页、资料详情）具备转发能力，内容正确。
- **G2** 标题与封面有统一生成规则，同一类对象产出格式一致，不依赖发版。
- **G3** 运营可独立调整文案与品牌封面（含时间窗、人群），无需前端介入。
- **G4** 分享带来的落地访问可归因、可统计。

### 非目标（本期不做）

- N1 不做 canvas 合成海报 / 带小程序码的分享长图。
- N2 不做分享激励、排行榜、裂变任务（现有「分享有礼」邀请体系保持原样）。
- N3 不改动 `pages.json` / `definePage` 的静态标题体系。
- N4 不给练习进行中、支付、登录等页面加转发。

---

## 5. 方案选型

### 5.1 候选方案

| 方案 | 形态 | 优点 | 缺点 |
| --- | --- | --- | --- |
| **A 端内硬编码** | 每个页面 `onShareAppMessage` 里写死字符串 | 最快，零后端 | 改文案要发版；无统计；页面多了重复代码 |
| **B 新建 share_config 表** | 新表 + 新接口 + 管理端新页面 | 语义最干净 | 新表+迁移+CRUD+管理端页面，成本最高；与 CMS 运营位能力重叠 |
| **C 复用 `cms_slot`** | 新增 `slot_type='share'`，`scene` 区分页面 | 零迁移；已有管理端、时间窗、分群、频次、统计；分享点击可直接进运营位统计 | `slot_type` 语义扩展，需要在管理端补枚举值 |
| **D 复用 `sys_config`** | 仿邀请文案池，`type=SHARE` | 改动最小 | 是键值对，无时间窗/分群/优先级/统计；运营配置体验差 |

### 5.2 结论：**C 为主 + A 作端内兜底**

理由：

1. `cms_slot` 现有字段完全覆盖分享场景需求（见 §7.1），**无需迁移**。
2. 后端已存在用户端只读接口与行为上报接口（见 §8），**无需新增接口**。
3. 管理端已有运营位页面 `frontend/apps/web-antdv-next/src/views/cms/slot/index.vue`。
4. 分享点击可复用 `POST /cms/slots/{pk}/log {action:1}`，直接落到 `cms_slot_log`。
5. 端内仍保留一份常量兜底，保证"运营没配"时分享内容不为空。

> 若评审更看重"分享"与"运营位"语义分离，可退化为方案 B；本方案的分层 resolver 与前端接口设计不受影响，只换配置读取源。

---

## 6. 总体设计

### 6.1 三层数据源

| 优先级 | 层 | 数据来源 | 维护者 | 适用对象 |
| --- | --- | --- | --- | --- |
| 1（最高） | **实体层** | 题库 `name / cover_url / q_count`；资料 `title / images[0]`；知识点 `name / 题量`；拼团 `team` | 内容运营（已有数据） | 有明确业务对象的页面 |
| 2 | **场景层** | `cms_slot` 中 `slot_type='share'`，按 `scene` 匹配，取 `title` + `image_url` + `extra.title_tpl` | 运营（现有后台） | 首页、资料大厅等无实体页面；也可覆盖实体页文案 |
| 3（兜底） | **端内常量** | `mini/src/constants/share.ts` 的 `scene → {title, image}` | 前端（写一次） | 保证永不空 |

**核心原则：场景层只提供"标题模板 + 封面"，标题里的变量由实体层填充。**

这样运营改文案不用发版，题库换封面也不用运营动。

### 6.2 解析优先级（resolver）

```
最终 title  =  实体生成的 title
             || 场景 title_tpl 渲染实体变量
             || 场景 title（纯文案）
             || 端内常量

最终 image  =  实体 cover
             || 场景 image_url
             || 端内常量默认图

最终 path   =  页面路径 + 业务参数 + 统一归因参数（from / sharer / invite_code）
```

### 6.3 为什么不能写进 `pages.json` / `definePage`

- 那里只有**静态字符串**，拿不到运行时实体数据（题库名、题量）。
- 分享标题与导航标题**天然不同**：导航是「我的错题」，分享应是「我攒了 300 道错题，一起复盘」。
- 运营改文案需要发版，与 G3 冲突。

---

## 7. 数据设计

### 7.1 `cms_slot` 字段映射

| 分享需求 | 现有字段 | 说明 |
| --- | --- | --- |
| 场景 | `scene` | 约定 `share_<语义>` 前缀，见 §7.2 |
| 形态 | `slot_type` | 新增枚举值 `share` |
| 文案 | `title` / `subtitle` | `title` 为纯文案标题；`subtitle` 备用 |
| 封面 | `image_url` | 必须是 **https + 5:4** |
| 标题模板 | `extra.title_tpl` | 见 §7.4 |
| 兜底封面 | `extra.fallback_image` | 可选，覆盖端内默认图 |
| 生效时间 | `start_time` / `end_time` | 复用，支持活动期文案 |
| 优先级 | `priority` | 复用，多条命中取最大 |
| 人群 | `target_user_type` / `target_min_member_level` | 复用（新老用户/会员文案） |
| 统计 | `id` → `cms_slot_log` | 复用行为上报 |

后端 `slot_type` 注释需同步更新：
`backend/app/cms/model/slot.py:27`、`schema/slot.py:16` 的 `curtain/banner/popup/splash/float/notice` → 追加 `share`。

管理端 `frontend/apps/web-antdv-next/src/views/cms/slot/data.ts` 需补：
`SLOT_TYPE_MAP` 增加 `share: { color: 'blue', label: '分享卡' }`，`slot_type` 选项同步。

### 7.2 scene 命名规范

```
share_<页面语义>[_<细分>]
```

只允许小写字母、数字、下划线；一个 scene 对应一个页面的分享默认内容。

### 7.3 `extra` 字段约定

```json
{
  "title_tpl": "「{name}」{count} 题 · 一起来刷",
  "fallback_image": "https://cdn.xxx.com/share/bank-default-5x4.png",
  "timeline": false
}
```

- 未声明的键一律忽略（向后兼容）。
- `timeline: true` 才允许该页面开放朋友圈，默认 `false`（见 §9.6）。

### 7.4 标题模板语法

| 占位符 | 含义 | 缺省行为 |
| --- | --- | --- |
| `{name}` | 实体名称（题库名/知识点名/资料名） | 为空则整段降级到下一优先级 |
| `{count}` | 题量 | 为 0 或空则去掉数量短语 |
| `{org}` | 机构/作者（资料） | 同上 |
| `{brand}` | 品牌名常量「一知行卷」 | 恒有值 |

规则：

1. 只做**字面替换**，不引入表达式，避免运营配错导致渲染异常。
2. 替换后长度上限 **40 个汉字**（微信标题过长会被截断），超出按 38 字 + `…` 截断。
3. 模板渲染结果为空的，视为"未配置"，继续降级。

### 7.5 封面规范

| 项 | 规范 |
| --- | --- |
| 比例 | 5:4（强约束，微信按此裁切） |
| 尺寸 | 输出 750×600，向下兼容 500×400 |
| 格式 | JPG（照片类）/ PNG（含文字时），单图建议压到 200KB 内 |
| 协议 | 必须 `https`（http 在部分基础库不展示，会回落截图） |
| 文字安全区 | 上下各留 8% 边距，主体信息居中，避免被裁 |
| 兜底 | 实体封面 → `extra.fallback_image` → 端内品牌图 |

> 题库 `cover_url` 现有图多为 1:1 或 3:2，直接用于分享会被裁掉上下。P0 阶段接受裁切（微信居中裁），
> P2 再评估"为题库单独上传一版 5:4 分享图"或用 canvas 合成。

---

## 8. 接口设计

### 8.1 读取（复用，无新增）

```
GET /api/v1/cms/slots/active?scene=share_bank_detail
```

- 已存在：`backend/app/cms/api/v1/slot.py:15-24`，**支持未登录**（未登录跳过分群与频次校验）。
- 返回 `list[GetActiveSlot]`，含 `id / code / slot_type / scene / title / subtitle / image_url / jump_type / jump_target / jump_extra / can_close / priority / extra`。
- 小程序 SDK 已封装：`api.getActiveSlots({ query: { scene } })`（`mini/src/api/endpoints/system.ts:57`）。

前端拿到列表后**本地过滤** `slot_type === 'share'`，与现有 `CmsCurtain` 的做法一致（`mini/src/pkg/shared/components/CmsCurtain.vue:58`）。

### 8.2 上报（复用，无新增）

```
POST /api/v1/cms/slots/{pk}/log   { action: 1, scene: "share_bank_detail" }
```

- `action`：`0` 曝光 / `1` 点击 / `2` 关闭。分享场景只用 `0`（分享面板出现）和 `1`（点了转发），不用 `2`。
- 已封装：`api.reportAction(...)`（`system.ts:61`）。
- 落地为 `cms_slot_log`，管理端 `GET /api/v1/cms/admin/slots/{pk}/stats` 可直接看出 CRT。

### 8.3 缓存策略

- 小程序端按 `scene` 缓存在**内存**（模块级 Map），带 5 分钟 TTL，冷启动重拉。
- 不做本地持久化缓存：分享文案属于运营配置，宁可偶发多一次请求，也不要长期展示过期文案。
- 分享回调内**只读内存**，绝不发请求（见 §9.3）。

### 8.4 结论

**P0 / P1 不需要新增任何后端接口或表结构。** 仅需：

1. 后端两处 `slot_type` 注释追加 `share`（注释级，无逻辑改动）。
2. 管理端运营位表单的枚举项补 `share`。

---

## 9. 前端设计

### 9.1 新增文件

| 文件 | 作用 |
| --- | --- |
| `mini/src/composables/useShare.ts` | 统一声明转发、解析内容、注入归因参数、上报统计 |
| `mini/src/constants/share.ts` | scene → `{ title, image, timeline }` 端内兜底常量 + 品牌默认 5:4 图 |
| `mini/tests/share-content.test.cjs` | resolver 优先级、模板渲染、截断、路径拼装单测 |

### 9.2 `useShare` 接口

```ts
useShare({
  scene: 'share_bank_detail',                        // 必填，对应 cms_slot.scene
  title: () => bank.value ? `${bank.value.name}｜${bank.value.q_count_cache} 题` : '',  // 实体标题
  image: () => bank.value?.cover_url || '',          // 实体封面
  path: () => `/pkg/practice/bank-detail/index?id=${bankId.value}`,
  query: () => ({ sharer: userStore.userId }),       // 额外归因参数，自动合并
  enabled: () => !!bank.value,                       // 数据未就绪时先返回兜底内容
})
```

行为：

- 自动注册 `onShareAppMessage`；仅当最终 `extra.timeline === true` 时额外注册 `onShareTimeline`。
- 内部完成 §6.2 的三级降级。
- 用户点转发时调一次 `reportAction({ action: 1 })`（fire-and-forget，失败静默）。

### 9.3 关键实现约束

1. **分享回调里不要 `await`。** 场景配置必须在 `onLoad` 预热到 `ref`，回调内同步读。
   （微信部分基础库支持回调返回 Promise，但 uni-app 编译层是否透传需真机验证，不作为设计前提。）
2. **数据未就绪也要能返回内容。** 用户可能在详情加载完成前就点转发，此时 `enabled()` 为 `false`，
   应返回端内兜底文案 + 默认图，而不是空对象。
3. **`path` 只拼一次。** 业务参数与归因参数合并后再 `encodeURIComponent`，避免重复 `?`。
4. 组件卸载后不再上报（用现有 `disposed` 模式）。

### 9.4 分享路径与参数

标准形态：

```
/pkg/practice/bank-detail/index?id=123&from=share&sharer=456[&invite_code=abc]
```

- `from=share`：落地页据此区分来源，用于埋点。
- `sharer`：分享者用户 ID，用于归因；未登录分享则不带。
- `invite_code`：**仅当用户有邀请码且属于邀请活动场景时带**，不要所有分享都塞。
- 落地侧**已有全局捕获**：`App.vue:65-78` 的 `onShow` 会调 `captureInviteCode(options.query)`
  并处理冷启动路由，因此参数命名必须与 `mini/src/utils/inviteReferral.ts` 保持一致。

### 9.5 落地页兼容（重点）

分享是**冷启动**入口，落地页必须能应对三种状态：

| 状态 | 要求 |
| --- | --- |
| 未登录 | 页面首屏不空白：展示只读预览 + 「登录后继续」，不直接弹登录 Modal 打断 |
| 已登录但无权益 | 题库/知识点有 `membershipAccess` 门槛（见 `pkg/practice/bank-detail/index.vue:15`），需展示"试做 N 题 + 解锁引导"，不能白屏 |
| 数据加载失败 | 展示 `ErrorState` + 重试，而不是无限骨架屏 |

> 这是本期最容易漏掉的一环：**分享出去点开白屏，等于拉新失败**。P0 验收必须真机走一遍未登录路径。

### 9.6 朋友圈（`onShareTimeline`）规则

默认**关闭**，仅当 `extra.timeline === true` 时开启。开启前提：

- 页面在单页模式下可正常渲染（无 tabBar 依赖、无必须登录的接口）。
- 只允许纯展示页：刷题首页、资料大厅、资料详情。
- 朋友圈只能带 `query`，因此分享的是"页面 + 少量参数"，不能指定其他 path。

---

## 10. 场景清单

| scene | 承载页面（path） | 标题策略 | 封面策略 | 朋友圈 |
| --- | --- | --- | --- | --- |
| `share_bank_detail` | `/pkg/practice/bank-detail/index?id=` | `「{name}」{count} 题 · 一起来刷` | 题库 `cover_url` → 分类默认 → 品牌图 | 否 |
| `share_kp_detail` | `/pkg/practice/kp-detail/index?point_id=` | `{name} 专项练习，{count} 题可刷` | 领域默认图 | 否 |
| `share_practice_home` | `/pages/practice/index`（tabBar） | 运营文案，兜底 `一知行卷 · 高效刷题` | 品牌 5:4 图 | **是** |
| `share_resource_detail` | `/pkg/resource/detail/index?id=` | 资料名（现有逻辑保留） | `images[0]`（补齐 5:4 校验） | 是 |
| `share_resource_hall` | `/pkg/resource/index` | `资料大厅 · 考研资料免费领` | 品牌 5:4 图 | 是 |
| `share_group_buy` | `/pkg/mine/group-buy/index?code=` | 现有拼团文案（保留） | **新增**默认图 | 否 |
| `share_invite` | `/pkg/mine/share-gift/index` | 现有文案池（**保持现状，不并入本期**） | 文案池 | 否 |

> 「分享有礼」涉及邀请奖励与风控，本期**不迁移**到新 resolver，避免影响现有归因链路；后续可平滑并入。

---

## 11. 关键页面改造细节

### 11.1 题库详情 `pkg/practice/bank-detail/index.vue`

1. 接入 `useShare`（`scene: 'share_bank_detail'`）。
2. **补齐封面渲染**：`cover_url` 有值时用于页面头部；为空时用现有主题色卡，避免布局跳动。
3. 分享图优先 `cover_url`。
4. 校验落地未登录/无权益时的预览态（现有 `membershipAccess` 逻辑 + 只读预览）。

### 11.2 知识点详情 `pkg/practice/kp-detail/index.vue`

1. 接入 `useShare`（`point_id` 优先、`id` 兼容，与现有 `onLoad` 一致：`kp-detail/index.vue:510`）。
2. 无专属封面，用领域默认图。
3. 标题带题量，便于好友判断体量。

### 11.3 刷题首页 `pages/practice/index.vue`

1. tabBar 页面，`type: "home"`、`disableScroll: true`。
2. 仅用场景配置 + 端内兜底，不涉及实体数据。
3. 开启朋友圈（单页模式下需验证首屏无登录依赖）。
4. 注意：从分享进入首页后 `onLoad` 的 query 与 tabBar 切换的关系需真机验证。

### 11.4 资料详情 `pkg/resource/detail/index.vue`

现有实现已可用，改造点：

1. 抽到 `useShare`，统一补 `from/sharer` 归因参数。
2. `images[0]` 增加 5:4 校验：比例明显不符时不传 `imageUrl`（让微信截图）还是传（裁切）—— **待确认 Q4**。

### 11.5 拼团 `pkg/mine/group-buy/index.vue`

1. 保留现有动态标题（含人数与模板名，转化导向明确）。
2. **补 `imageUrl`**（当前缺，会截到"立即拼团"按钮），使用 `share_group_buy` 场景图。
3. 不做完整迁移，只补封面 + 归因参数。

---

## 12. 数据与埋点

| 指标 | 口径 | 数据源 |
| --- | --- | --- |
| 分享面板曝光 | `action=0` 上报次数 | `cms_slot_log` |
| 分享点击 | `action=1` 上报次数（**用户点了转发**，不等于分享成功） | `cms_slot_log` |
| 落地访问 | 落地页解析到 `from=share` 的 PV/UV | 需前端埋点（本期只做参数透传，不建表） |
| 归因转化 | `sharer` + 后续注册/付费关联 | 依赖现有邀请/用户来源体系，本期仅透传 |

**明确做不到的**：微信不提供分享成功回调，因此"实际转发成功数"只能靠间接估算（落地 UV / 群 `shareTicket`），
任何"分享成功 N 次"的报表口径都需注明是**点击口径**。

---

## 13. 分期与验收

### P0（本期，1 天量级）

- [ ] `useShare.ts` + `constants/share.ts` + 单测
- [ ] 题库详情、知识点详情、刷题首页接入
- [ ] 题库详情补 `cover_url` 渲染
- [ ] 归因参数统一注入（`from` / `sharer`）

**验收**：
1. 四个页面右上角可转发，卡片有标题、有 5:4 封面（或兜底图）。
2. 未登录点开分享链接，页面首屏有内容、不白屏。
3. 题库 `cover_url` 为空时使用兜底图，卡片无空图。
4. `node tests/share-content.test.cjs` 通过；`pnpm check:design` 无新增阻断。

### P1（+0.5 天）

- [ ] 后端 `slot_type` 注释补 `share`
- [ ] 管理端运营位枚举补 `share`（label「分享卡」）
- [ ] 前端改为读 `/cms/slots/active` 场景配置，常量降为兜底
- [ ] 接入 `action=0/1` 上报

**验收**：运营在后台改一条 `share_bank_detail` 的标题/封面，小程序重启后生效，无需发版。

### P2（可选，1~2 天）

- [ ] canvas 合成 5:4 分享卡（封面底图 + 标题 + 题量 + 品牌角标）
- [ ] 成绩/报告类分享（"我刷了 100 题，正确率 82%"）——这是唯一必须合成图的场景
- [ ] 评估朋友圈在更多页面的可行性

---

## 14. 风险与待确认问题

| # | 问题 | 影响 | 建议 |
| --- | --- | --- | --- |
| Q1 | 未登录落地是否允许"只读预览题目"？ | 决定分享拉新效果与内容安全策略 | 需产品拍板；建议允许预览 3 题 |
| Q2 | 题库是否要单独维护一版 5:4 分享图？ | 直接影响卡片观感 | 建议 P2 评估，P0 先接受裁切 |
| Q3 | 分享是否统一带 `invite_code`？ | 关系邀请奖励归因，误带会造成脏数据 | 建议只在「分享有礼」链路带 |
| Q4 | 资料图非 5:4 时：传图被裁 vs 不传走截图？ | 影响资料分享观感 | 待评审定 |
| Q5 | 朋友圈是否只在 3 个纯展示页开放？ | 单页模式兼容风险 | 建议是，且需真机验证 |
| Q6 | 是否把「分享有礼」并入统一 resolver？ | 涉及奖励风控 | 建议本期不动 |

**技术风险**：

- `onShareAppMessage` 异步返回 Promise 的跨端一致性未验证 → 已用"预热 + 同步读"规避。
- 分包页面路径拼错会导致分享打开 404（小程序会提示页面不存在）→ 单测覆盖路径拼装。
- 网络图加载失败时微信会回落到截图 → 兜底图建议放 **CDN 稳定域名**，不要用小包内 base64。

---

## 15. 改动文件清单（预估）

### 前端（mini）

| 文件 | 改动 |
| --- | --- |
| `src/composables/useShare.ts` | 新增 |
| `src/constants/share.ts` | 新增 |
| `tests/share-content.test.cjs` | 新增 |
| `src/pkg/practice/bank-detail/index.vue` | 接入 + 补封面渲染 |
| `src/pkg/practice/kp-detail/index.vue` | 接入 |
| `src/pages/practice/index.vue` | 接入 |
| `src/pkg/resource/detail/index.vue` | 改造为 useShare |
| `src/pkg/mine/group-buy/index.vue` | 补 `imageUrl` + 归因参数 |

### 后端

| 文件 | 改动 |
| --- | --- |
| `backend/app/cms/model/slot.py` | 仅注释补 `share` |
| `backend/app/cms/schema/slot.py` | 仅注释补 `share` |

### 管理端

| 文件 | 改动 |
| --- | --- |
| `frontend/apps/web-antdv-next/src/views/cms/slot/data.ts` | `slot_type` 枚举 + label |

**无数据库迁移，无新增接口。**

---

## 16. 评审待办

1. 确认选型（方案 C 复用 `cms_slot`，还是方案 B 独立表）。
2. 回答 §14 的 Q1、Q3、Q4（影响落地页改造量与归因口径）。
3. 确认 P0 页面范围是否就这 4 个。
