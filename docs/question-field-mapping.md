| 前端字段 | 后端支持 | 说明 |
|---------|---------|------|
| bank_id | ✅ | 题库ID |
| type_id | ✅ | 题型ID (1-5) |
| chapter_id | ✅ | 章节ID |
| diff_id | ✅ | 难度ID |
| stem | ✅ | 题干 |
| score | ✅ | 分值 |
| answer_json | ✅ | 答案JSON结构 |
| answer_text | ✅ | 答案文本 |
| analysis | ✅ | 解析 |
| media_assets | ✅ | 媒体资源 |
| is_active | ✅ | 是否启用 |
| options | ✅ | 选项列表（选择题） |
| keyword | ✅ | 关键字 |
| source | ✅ | 来源 |
| year | ✅ | 年份 |
| **choice_type** | ❌ | 选择题类型（单选/多选/不定项）- **会被忽略** |
| **usage** | ❌ | 用途（全部/考试/练习）- **会被忽略** |
| **alias** | ❌ | 别名 - **会被忽略** |
| **stem_media** | ⚠️ | 应映射到 media_assets，但格式不匹配 |
