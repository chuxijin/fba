# Feishu Sheet

飞书电子表格集成插件，基于飞书开放平台「应用身份」（`tenant_access_token`）读写电子表格。

## 前置准备

1. 在[飞书开放平台](https://open.feishu.cn)创建企业自建应用，获取 `App ID` 与 `App Secret`
2. 为应用开通并**发布**以下权限：
   - `drive:drive`
   - `sheets:spreadsheet`
   - `sheets:spreadsheet:create`
   - 表格位于知识库时额外需要 `wiki:node:retrieve`
3. 把目标表格（或整个知识库）分享给该应用，权限设为「可编辑」

## 环境变量

```env
FEISHU_APP_ID=''
FEISHU_APP_SECRET=''
# 默认表格：支持 /sheets/ 直链、/wiki/ 知识库链接或裸 spreadsheet_token
FEISHU_SHEET_URL=''
# 默认子表：sheet_id 或子表名称（可留空，默认取第一个子表）
FEISHU_SHEET_ID=''
FEISHU_SHEET_NAME=''
```

## 接口

统一前缀：`/api/v1/feishu/sheet`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/sheets` | 获取子表列表 |
| GET | `/read` | 读取单元格数据 |
| POST | `/write` | 写入指定范围（覆盖） |
| POST | `/append` | 追加数据到数据区末尾（不影响表头） |
| POST | `/batch-append` | 批量追加，同一工作簿合并为一次请求 |
| POST | `/insert-rows` | 在指定位置插入空行 |
| PUT | `/style` | 设置单元格样式 |
| POST | `/dropdown` | 设置下拉列表 |
| GET | `/dropdown` | 查询下拉列表 |
| DELETE | `/dropdown` | 删除下拉列表 |
| PUT | `/resize` | 调整行高列宽 |

所有接口均需要登录鉴权。

## 使用示例

### 追加数据

```json
POST /api/v1/feishu/sheet/append
{
  "workbook": "https://xxx.feishu.cn/sheets/DOEXsIyBUh6ZhDtgb4mcj0KNnZe",
  "sheet": "笔记部分",
  "rows": [
    ["2026-09-18 10:00", "标题", "分类", "https://example.com", "待读", "脚本"]
  ],
  "header_rows": 1
}
```

### 批量追加（多子表合并请求）

```json
POST /api/v1/feishu/sheet/batch-append
{
  "jobs": [
    {"sheet": "笔记部分", "rows": [["", "A"]]},
    {"sheet": "刷题部分", "rows": [["", "B"]]}
  ]
}
```

### 设置表头样式

```json
PUT /api/v1/feishu/sheet/style
{
  "sheet": "笔记部分",
  "cell_range": "A1:F1",
  "style": {
    "bold": true,
    "font_color": "#FFFFFF",
    "background_color": "#4472C4",
    "horizontal_alignment": "center",
    "vertical_alignment": "middle",
    "border_type": "FULL_BORDER",
    "border_color": "#B7C9D9"
  }
}
```

### 设置下拉列表

```json
POST /api/v1/feishu/sheet/dropdown
{
  "sheet": "笔记部分",
  "cell_range": "E2:E1000",
  "options": ["待读", "已读", "搁置"]
}
```

## 在代码 / 定时任务中调用

```python
from backend.plugin.feishu.service.sheet_service import feishu_sheet_service

await feishu_sheet_service.append(
    workbook=settings.FEISHU_SHEET_URL,
    sheet='笔记部分',
    rows=[['2026-09-18 10:00', '标题', '分类', 'https://example.com', '待读', '脚本']],
)
```

## 说明

- `tenant_access_token` 缓存在 Redis（前缀 `FEISHU_TOKEN_REDIS_PREFIX`），有效期 2 小时，过期前 5 分钟自动刷新；Redis 不可用时会自动降级为进程内缓存 + 直连
- 写入范围统一使用 `sheet_id` 定位，不使用子表名称（子表可随时改名）
- 同一子表的并发追加会互相覆盖行号，请保证单写入者或加锁
- 单次 `batch_append` / `batch_write` 的 range 数量有服务端上限，数量很大时请分批调用
- 下拉选项不能包含英文逗号；开启高亮时会自动按默认配色循环填充
- **下拉范围不能超出子表的网格行数**（新建子表默认 200 行），否则报 `range exceeds grid limits`；需要更大范围时先用 `insert-rows` 扩容
- 单元格写入 URL 字符串会被飞书自动识别为可点击的超链接（存储为富文本 link 对象）
- 飞书没有公开的清空接口，`clear_values` 以空字符串覆盖实现

## 服务层能力（代码 / 定时任务调用）

| 方法 | 说明 |
| --- | --- |
| `list_sheets` / `find_sheet_by_title` | 子表列表 / 按名称查 id |
| `create_sheet` / `rename_sheet` | 新建 / 重命名子表 |
| `resolve_target` | 解析链接（支持 `/sheets/` 与 `/wiki/`）为 `(workbook_token, sheet_id)` |
| `read` / `write` / `batch_write` | 读写单元格 |
| `append` / `batch_append` | 追加到数据区末尾 / 多子表合并一次请求 |
| `find_last_row` | 最后一个非空行 |
| `insert_rows` | 在指定位置插入空行 |
| `clear_values` | 清空范围内容 |
| `build_style` / `set_style` | 构造并设置单元格样式 |
| `set_dropdown` / `get_dropdown` / `delete_dropdown` | 下拉列表 |
| `resize` / `set_dimension_visible` | 行列尺寸 / 隐藏显示 |

## plugin.toml 中的业务配置

`[settings]` 里另有一组「公考资源同步到飞书」的配置（`GONGKAO_FEISHU_*`），用于
`backend/app/mydrive/service/feishu_export_service.py`：

```toml
# 是否启用定时同步
GONGKAO_FEISHU_SYNC_ENABLED = true
# 资源类型 -> 子表名称（未列出的资源类型不参与同步，如已下线的「课程」）
GONGKAO_FEISHU_SHEET_MAP = [
    '笔记=笔记专栏',
    '真题=真题获取',
    '电子书=干货汇总',
    '软件=干货汇总',
    '其他=干货汇总',
    '干货=干货汇总',
]
# 分类来源
GONGKAO_FEISHU_CATEGORY_APP_CODE = 'youanshang'
GONGKAO_FEISHU_CATEGORY_TYPE = 'knowledge_point'
# 分类列下拉选项
GONGKAO_FEISHU_CATEGORY_OPTIONS = ['政治理论', '常识判断', '言语理解与表达', '数量关系', '判断推理', '资料分析', '申论', '面试']
# 来源随机权重（店铺购买仅在 GONGKAO_FEISHU_PAID_SHEETS 中出现）
GONGKAO_FEISHU_SOURCE_WEIGHTS = ['用户推荐=4', '网络获取=5', '店铺购买=1']
GONGKAO_FEISHU_PAID_SHEETS = ['真题获取', '干货汇总']
```

> ⚠️ `plugin.toml` 的 settings 只支持 `str / int / float / bool / list[str]`，**不支持字典**，
> 因此映射表与权重用 `键=值` 的字符串列表编码，由服务层解析。
> 这些配置项在 `backend/core/conf.py` 中声明为无默认值（`# 以下配置项均在 plugin.toml 中`），
> 若移除 plugin.toml 里的对应项会导致应用启动失败（与 `EMAIL_HOST` 等一致）。

## 定时任务

| 任务 | 说明 |
| --- | --- |
| `mydrive:init_feishu_sheet` | 初始化子表（重命名 / 表头 / 样式 / 下拉 / 隐藏 ID 列），幂等 |
| `mydrive:sync_resources_to_feishu_sheet` | 同步公考资源，beat 每日 03:00 触发，受 `GONGKAO_FEISHU_SYNC_ENABLED` 控制 |

