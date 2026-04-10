# 知识点内容生产规范（Tiptap JSON）

## 1. 目标

本文档用于统一 `sys_content` 的知识点内容写法，确保：

1. 内容可直接用于教学和解题。
2. 前端编辑器可稳定回显和继续编辑。
3. SQL 可重复执行（upsert），不因字段遗漏报错。

## 2. 适用范围

1. 表：`sys_content`
2. 分类来源：`sys_category`（`type = knowledge_point`）
3. 编辑器：`frontend/apps/web-antdv-next/src/components/TiptapEditor`

## 3. 数据约定（必须遵守）

1. `app_code`：当前内容管理页使用 `gongkao` 作为内容应用标识。
2. `category_id`：可关联到 `youanshang` 的知识点分类节点（按 `code` 查 `id`）。
3. `content_json`：主内容，必须写。
4. `content_html`：可先置 `NULL`，后续在前端打开并保存一次自动生成。
5. `view_count`：必须显式写入 `0`，否则可能触发非空约束报错。
6. `slug`：唯一键，使用稳定命名，不随标题频繁变动。

## 4. 文章结构标准（落地可解题）

每篇内容至少包含以下模块：

1. 题型定义与识别
2. 核心公式
3. 标准步骤
4. 例题完整推导
5. 易错点纠偏
6. 刷题建议

推荐顺序：

1. `heading`：标题
2. `callout`：核心结论
3. `blockMath`：关键公式
4. `columns`：题型特征与解法动作对照
5. `mermaidDiagram`：流程图
6. 正文与例题
7. `callout`：易错点

## 5. 公式写法规范（已验证）

为保证渲染稳定，优先使用教学表达式，少用集合符号。

推荐写法：

1. `至少一个 = A + B - 都满足`
2. `都不满足 = 总数 - 至少一个`
3. `三集合：至少一个 = A + B + C - AB - AC - BC + ABC`

不推荐写法（容易触发显示异常）：

1. 复杂的 `\cup`、`\cap` 连续表达
2. 公式块中混入过多解释性文本

## 6. 编辑器节点白名单（可直接用于 JSON）

已确认可用节点和关键属性如下：

1. `heading`，属性：`level`
2. `paragraph`
3. `bulletList` / `orderedList` / `listItem`
4. `callout`，属性：`backgroundColor`
5. `inlineMath`，属性：`latex`
6. `blockMath`，属性：`latex`
7. `mermaidDiagram`，属性：`code`
8. `columns`，属性：`cols`
9. `column`，属性：`index`

## 7. 最小 SQL 模板（upsert）

```sql
WITH category_node AS (
    SELECT id
    FROM sys_category
    WHERE app_code = 'youanshang'
      AND type = 'knowledge_point'
      AND code = :category_code
)
INSERT INTO sys_content (
    app_code,
    title,
    slug,
    content_json,
    content_html,
    summary,
    category_id,
    tags,
    is_pinned,
    is_public,
    is_published,
    publish_time,
    view_count,
    sort_order,
    extra,
    created_by,
    created_time
)
SELECT
    'gongkao',
    :title,
    :slug,
    CAST(:content_json AS jsonb),
    NULL,
    :summary,
    category_node.id,
    CAST(:tags AS jsonb),
    FALSE,
    TRUE,
    TRUE,
    NOW(),
    0,
    0,
    CAST(:extra AS jsonb),
    1,
    NOW()
FROM category_node
ON CONFLICT (slug)
DO UPDATE SET
    title = EXCLUDED.title,
    content_json = EXCLUDED.content_json,
    content_html = EXCLUDED.content_html,
    summary = EXCLUDED.summary,
    category_id = EXCLUDED.category_id,
    tags = EXCLUDED.tags,
    is_pinned = EXCLUDED.is_pinned,
    is_public = EXCLUDED.is_public,
    is_published = EXCLUDED.is_published,
    publish_time = EXCLUDED.publish_time,
    view_count = EXCLUDED.view_count,
    sort_order = EXCLUDED.sort_order,
    extra = EXCLUDED.extra,
    updated_by = 1,
    updated_time = NOW();
```

## 8. 上线前检查清单

1. `slug` 唯一且命名一致。
2. `category_id` 指向正确知识点节点。
3. `content_json` 能在前端正常打开，不报节点错误。
4. `callout / blockMath / mermaid / columns` 显示正常。
5. 保存一次后可自动回填 `content_html`。
6. 例题能完整算出结果，不只给结论。

## 9. 常见报错与处理

1. `view_count` 非空约束报错：SQL 中显式写 `view_count = 0`。
2. `slug` 冲突：更换 slug 或使用 upsert 覆盖。
3. 前端打开为空：检查 `content_json` 节点名是否在白名单内。
4. 公式显示异常：改为教学表达式，避免复杂集合符号。
5. 分类不显示：确认内容页使用的 `app_code` 与分类树读取策略是否一致。

## 10. 命名建议

1. 标题：`知识点名称`
2. slug：`kp-专题-子专题`，例如 `kp-travel-meet`
3. tags：按学习路径给，建议从大到小
4. extra：至少保留 `content_type`、`category_code`、`source`

