# AppFlowy 类功能数据库设计

## 核心模型概览

```
Workspace（工作空间）
    └── Page（页面/文档）
            └── Block（内容块）
                    └── Block（子块，可无限嵌套）
```

## 1. 工作空间表 (jia_workspace)

```sql
CREATE TABLE jia_workspace (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,           -- 工作空间名称
    icon VARCHAR(50),                      -- 图标（emoji 或图标名）
    cover_image VARCHAR(255),              -- 封面图片
    settings JSONB DEFAULT '{}',           -- 工作空间设置

    -- 审计字段
    created_by INT NOT NULL,
    created_time TIMESTAMP DEFAULT NOW(),
    updated_time TIMESTAMP
);
```

## 2. 页面表 (jia_page)

```sql
CREATE TABLE jia_page (
    id SERIAL PRIMARY KEY,
    workspace_id INT NOT NULL REFERENCES jia_workspace(id),
    parent_id INT REFERENCES jia_page(id), -- 父页面（支持嵌套）

    -- 基本信息
    title VARCHAR(255) NOT NULL DEFAULT '无标题',
    icon VARCHAR(50),                       -- 页标 emoji
    cover_image VARCHAR(255),               -- 封面图

    -- 页面类型
    page_type VARCHAR(20) DEFAULT 'document', -- document/database/board/calendar

    -- 排序和路径
    sort_order INT DEFAULT 0,               -- 同级排序
    path VARCHAR(500),                      -- 物化路径，如 /1/5/12/
    depth INT DEFAULT 0,                    -- 嵌套深度

    -- 状态
    is_archived BOOLEAN DEFAULT FALSE,      -- 是否归档
    is_favorite BOOLEAN DEFAULT FALSE,      -- 是否收藏
    is_deleted BOOLEAN DEFAULT FALSE,       -- 软删除
    deleted_time TIMESTAMP,

    -- 权限（简化版）
    is_public BOOLEAN DEFAULT FALSE,        -- 是否公开

    -- 审计字段
    created_by INT NOT NULL,
    created_time TIMESTAMP DEFAULT NOW(),
    updated_time TIMESTAMP,

    -- 索引
    INDEX idx_workspace (workspace_id),
    INDEX idx_parent (parent_id),
    INDEX idx_path (path)
);
```

## 3. 块表 (jia_block) - 核心！

```sql
CREATE TABLE jia_block (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),  -- 使用 UUID 便于客户端生成
    page_id INT NOT NULL REFERENCES jia_page(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES jia_block(id),        -- 父块（支持嵌套）

    -- 块类型
    type VARCHAR(30) NOT NULL,              -- 见下方块类型列表

    -- 块内容（JSONB 灵活存储）
    content JSONB NOT NULL DEFAULT '{}',

    -- 排序
    sort_order INT DEFAULT 0,               -- 同级内排序

    -- 折叠状态
    is_collapsed BOOLEAN DEFAULT FALSE,     -- 是否折叠子块

    -- 审计
    created_time TIMESTAMP DEFAULT NOW(),
    updated_time TIMESTAMP,

    -- 索引
    INDEX idx_page (page_id),
    INDEX idx_parent (parent_id),
    INDEX idx_type (type)
);

-- 块类型枚举说明：
-- text          普通文本/段落
-- heading_1     一级标题
-- heading_2     二级标题
-- heading_3     三级标题
-- bulleted_list 无序列表项
-- numbered_list 有序列表项
-- todo          待办事项
-- toggle        折叠块
-- quote         引用
-- divider       分割线
-- callout       提示框
-- code          代码块
-- image         图片
-- video         视频
-- file          文件附件
-- bookmark      书签/链接预览
-- table         简单表格
-- database      数据库引用
-- embed         嵌入内容
-- math          数学公式
-- page_link     页面链接
```

## 4. 块内容 JSONB 结构示例

```json
// text 块
{
    "rich_text": [
        {"type": "text", "text": "Hello ", "styles": {}},
        {"type": "text", "text": "World", "styles": {"bold": true, "color": "red"}}
    ]
}

// heading_1 块
{
    "rich_text": [{"type": "text", "text": "我的标题"}],
    "level": 1
}

// todo 块
{
    "rich_text": [{"type": "text", "text": "买牛奶"}],
    "checked": false
}

// code 块
{
    "rich_text": [{"type": "text", "text": "print('hello')"}],
    "language": "python"
}

// image 块
{
    "url": "/uploads/xxx.png",
    "caption": "图片说明",
    "width": 600
}

// callout 块
{
    "rich_text": [{"type": "text", "text": "注意事项"}],
    "icon": "⚠️",
    "color": "yellow_background"
}

// bookmark 块
{
    "url": "https://example.com",
    "title": "Example Site",
    "description": "An example website",
    "image": "https://example.com/og.png"
}
```

## 5. 数据库功能（类 Notion Database）

### 5.1 数据库定义表 (jia_database)

```sql
CREATE TABLE jia_database (
    id SERIAL PRIMARY KEY,
    page_id INT NOT NULL REFERENCES jia_page(id), -- 关联的页面
    name VARCHAR(100),

    -- 属性定义（列）
    properties JSONB NOT NULL DEFAULT '[]',

    -- 示例 properties:
    -- [
    --     {"id": "title", "name": "名称", "type": "title"},
    --     {"id": "status", "name": "状态", "type": "select", "options": [...]},
    --     {"id": "date", "name": "日期", "type": "date"},
    --     {"id": "tags", "name": "标签", "type": "multi_select", "options": [...]}
    -- ]

    created_time TIMESTAMP DEFAULT NOW(),
    updated_time TIMESTAMP
);
```

### 5.2 数据库行表 (jia_database_row)

```sql
CREATE TABLE jia_database_row (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    database_id INT NOT NULL REFERENCES jia_database(id) ON DELETE CASCADE,

    -- 行数据（键是 property id）
    properties JSONB NOT NULL DEFAULT '{}',

    -- 示例:
    -- {
    --     "title": "任务1",
    --     "status": "进行中",
    --     "date": "2024-01-15",
    --     "tags": ["重要", "工作"]
    -- }

    -- 每行可以展开为页面
    page_id INT REFERENCES jia_page(id),  -- 如果展开了，关联的页面

    sort_order INT DEFAULT 0,
    is_deleted BOOLEAN DEFAULT FALSE,

    created_time TIMESTAMP DEFAULT NOW(),
    updated_time TIMESTAMP,

    INDEX idx_database (database_id)
);
```

### 5.3 数据库视图表 (jia_database_view)

```sql
CREATE TABLE jia_database_view (
    id SERIAL PRIMARY KEY,
    database_id INT NOT NULL REFERENCES jia_database(id) ON DELETE CASCADE,

    name VARCHAR(100) NOT NULL,
    view_type VARCHAR(20) NOT NULL,     -- table/board/calendar/gallery/list

    -- 视图配置
    config JSONB NOT NULL DEFAULT '{}',

    -- table 视图 config 示例:
    -- {
    --     "visible_properties": ["title", "status", "date"],
    --     "property_widths": {"title": 200, "status": 120},
    --     "sorts": [{"property": "date", "direction": "desc"}],
    --     "filters": [{"property": "status", "operator": "equals", "value": "进行中"}]
    -- }

    -- board 视图 config 示例:
    -- {
    --     "group_by": "status",
    --     "visible_properties": ["title", "date"],
    --     "hide_empty_groups": false
    -- }

    sort_order INT DEFAULT 0,

    created_time TIMESTAMP DEFAULT NOW(),
    updated_time TIMESTAMP
);
```

## 6. 属性类型说明

| 类型 | 说明 | 值示例 |
|------|------|--------|
| title | 标题（必须有一个） | "任务名称" |
| text | 纯文本 | "备注内容" |
| number | 数字 | 42.5 |
| select | 单选 | "进行中" |
| multi_select | 多选 | ["标签1", "标签2"] |
| date | 日期/时间 | "2024-01-15" 或 {"start": "...", "end": "..."} |
| checkbox | 复选框 | true/false |
| url | 链接 | "https://..." |
| email | 邮箱 | "test@example.com" |
| phone | 电话 | "13800138000" |
| person | 用户 | [1, 2] (user ids) |
| files | 文件 | [{"name": "...", "url": "..."}] |
| relation | 关联其他数据库 | ["row_uuid_1", "row_uuid_2"] |
| formula | 公式 | (计算值，只读) |
| created_time | 创建时间 | (自动) |
| updated_time | 更新时间 | (自动) |

## 7. 版本历史表（可选）

```sql
CREATE TABLE jia_block_history (
    id SERIAL PRIMARY KEY,
    block_id UUID NOT NULL,
    page_id INT NOT NULL,

    -- 快照
    content JSONB NOT NULL,

    -- 操作信息
    operation VARCHAR(20),              -- create/update/delete
    changed_by INT NOT NULL,
    changed_time TIMESTAMP DEFAULT NOW(),

    INDEX idx_block (block_id),
    INDEX idx_page (page_id)
);
```

## 8. SQLAlchemy 模型示例

```python
# backend/app/jia/model/workspace.py
from __future__ import annotations

from sqlalchemy import String, Boolean, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from backend.common.model import Base, UserMixin, id_key


class Workspace(Base, UserMixin):
    """工作空间表"""
    __tablename__ = 'jia_workspace'

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(String(100), comment='工作空间名称')
    icon: Mapped[str | None] = mapped_column(String(50), default=None)
    cover_image: Mapped[str | None] = mapped_column(String(255), default=None)
    settings: Mapped[dict] = mapped_column(JSONB, default={})

    # 关系
    pages: Mapped[list[Page]] = relationship(back_populates='workspace', default_factory=list)


class Page(Base, UserMixin):
    """页面表"""
    __tablename__ = 'jia_page'

    id: Mapped[id_key] = mapped_column(init=False)
    workspace_id: Mapped[int] = mapped_column(ForeignKey('jia_workspace.id'))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey('jia_page.id'), default=None)

    title: Mapped[str] = mapped_column(String(255), default='无标题')
    icon: Mapped[str | None] = mapped_column(String(50), default=None)
    cover_image: Mapped[str | None] = mapped_column(String(255), default=None)
    page_type: Mapped[str] = mapped_column(String(20), default='document')

    sort_order: Mapped[int] = mapped_column(default=0)
    path: Mapped[str | None] = mapped_column(String(500), default=None)
    depth: Mapped[int] = mapped_column(default=0)

    is_archived: Mapped[bool] = mapped_column(default=False)
    is_favorite: Mapped[bool] = mapped_column(default=False)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    is_public: Mapped[bool] = mapped_column(default=False)

    # 关系
    workspace: Mapped[Workspace] = relationship(back_populates='pages')
    blocks: Mapped[list[Block]] = relationship(back_populates='page', default_factory=list)
    children: Mapped[list[Page]] = relationship(back_populates='parent', default_factory=list)
    parent: Mapped[Page | None] = relationship(back_populates='children', remote_side=[id])


class Block(Base):
    """内容块表"""
    __tablename__ = 'jia_block'

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    page_id: Mapped[int] = mapped_column(ForeignKey('jia_page.id', ondelete='CASCADE'))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('jia_block.id'), default=None)

    type: Mapped[str] = mapped_column(String(30))
    content: Mapped[dict] = mapped_column(JSONB, default={})
    sort_order: Mapped[int] = mapped_column(default=0)
    is_collapsed: Mapped[bool] = mapped_column(default=False)

    created_time: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_time: Mapped[datetime | None] = mapped_column(default=None, onupdate=datetime.now)

    # 关系
    page: Mapped[Page] = relationship(back_populates='blocks')
    children: Mapped[list[Block]] = relationship(back_populates='parent', default_factory=list)
    parent: Mapped[Block | None] = relationship(back_populates='children', remote_side=[id])
```

## 9. API 设计建议

```
# 页面
GET    /api/v1/workspaces/{workspace_id}/pages          # 获取页面树
POST   /api/v1/workspaces/{workspace_id}/pages          # 创建页面
GET    /api/v1/pages/{page_id}                          # 获取页面详情（含块）
PUT    /api/v1/pages/{page_id}                          # 更新页面
DELETE /api/v1/pages/{page_id}                          # 删除页面
POST   /api/v1/pages/{page_id}/move                     # 移动页面

# 块
GET    /api/v1/pages/{page_id}/blocks                   # 获取页面所有块
POST   /api/v1/pages/{page_id}/blocks                   # 创建块
PUT    /api/v1/blocks/{block_id}                        # 更新块
DELETE /api/v1/blocks/{block_id}                        # 删除块
POST   /api/v1/blocks/{block_id}/move                   # 移动块
POST   /api/v1/blocks/batch                             # 批量操作块

# 数据库
GET    /api/v1/databases/{database_id}                  # 获取数据库定义
GET    /api/v1/databases/{database_id}/rows             # 获取数据库行
POST   /api/v1/databases/{database_id}/rows             # 创建行
PUT    /api/v1/database-rows/{row_id}                   # 更新行
DELETE /api/v1/database-rows/{row_id}                   # 删除行
```

## 10. 前端数据结构建议

```typescript
// 块的前端结构
interface Block {
  id: string;           // UUID
  type: BlockType;
  content: BlockContent;
  children: Block[];    // 子块（树形结构）
  isCollapsed: boolean;
}

// 富文本结构
interface RichText {
  type: 'text' | 'mention' | 'equation';
  text?: string;
  styles?: {
    bold?: boolean;
    italic?: boolean;
    underline?: boolean;
    strikethrough?: boolean;
    code?: boolean;
    color?: string;
    backgroundColor?: string;
  };
  mention?: { type: 'page' | 'user'; id: string };
}
```

## 总结

这个设计的特点：
1. **灵活性** - 使用 JSONB 存储块内容，可以支持任意块类型
2. **性能** - 树形结构使用邻接表，查询简单
3. **扩展性** - 数据库功能独立设计，可以后续添加
4. **简单** - 核心只有 4 张表：workspace, page, block, database

建议 MVP 阶段先实现：
1. 页面的 CRUD 和嵌套
2. 基础块类型（text, heading, list, todo, image）
3. 块的拖拽排序

后续再添加：
- 数据库功能
- 协作功能
- 版本历史
- 导出/导入
