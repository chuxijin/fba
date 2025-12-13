# 题库系统 API 接口文档

## 1. 题目管理模块

| 接口地址 | 方法 | 功能说明 | 关键参数 |
|---------|------|---------|---------|
| `/api/v1/qbank/questions` | GET | 批量获取题目列表（支持筛选、分页） | `ids`, `bank_id`, `chapter_id`, `type`, `difficulty`, `page`, `size`, **`include_answer`** |
| `/api/v1/qbank/questions/{question_id}` | GET | 获取题目详情（管理端，含答案） | - |
| `/api/v1/qbank/practice/banks/{bank_id}/questions` | GET | 获取题库的题目列表（刷题专用，不含答案） | `type`, `difficulty` |
| `/api/v1/qbank/practice/chapters/{chapter_id}/questions` | GET | 获取章节的题目列表（刷题专用，不含答案） | `type`, `difficulty` |
| `/api/v1/qbank/practice/questions/{question_id}` | GET | 获取题目详情（刷题专用，不含答案） | - |
| `/api/v1/qbank/practice/questions/{question_id}/analysis` | GET | 获取题目解析（含答案） | - |
| `/api/v1/qbank/practice/submit` | POST | 批量提交答案并获取判分结果 | `answers[]`, `include_analysis` |

**🔥 重点说明：**
- `include_answer=true` 用于查看历史记录时获取完整题目（含答案和解析）
- 刷题接口不返回答案，避免作弊
- 提交接口返回判分结果和解析内容

---

## 2. 练习会话模块

| 接口地址 | 方法 | 功能说明 | 关键参数 |
|---------|------|---------|---------|
| `/api/v1/qbank/practice/sessions` | POST | 创建练习会话（开始练习） | `session_type`, `bank_id`, `chapter_id`, `question_ids`, `total_count` |
| `/api/v1/qbank/practice/sessions/{session_id}` | GET | 获取会话详情（继续答题/查看历史） | - |
| `/api/v1/qbank/practice/sessions/{session_id}` | PUT | 更新会话统计（答题过程中实时更新） | `completed_count`, `correct_count`, `wrong_count`, `total_time` |
| `/api/v1/qbank/practice/sessions/{session_id}` | DELETE | 删除练习会话（支持滑动删除） | - |
| `/api/v1/qbank/practice/sessions/{session_id}/submit` | POST | 提交练习（标记为已完成） | `score` |
| `/api/v1/qbank/practice/sessions` | GET | 获取练习会话列表（练习历史） | `page`, `size`, `status`, `session_type` |
| `/api/v1/qbank/practice/records` | POST | 创建单条答题记录（答题时实时保存） | `session_id`, `question_id`, `user_answer`, `is_correct`, `answer_time` |
| `/api/v1/qbank/practice/records/batch` | POST | 批量创建答题记录（提交时调用，先删除旧记录） | `session_id`, `records[]` |
| `/api/v1/qbank/practice/sessions/{session_id}/records` | GET | 获取会话的答题记录 | - |
| `/api/v1/qbank/practice/sessions/{session_id}/answer-card` | GET | 获取答题卡数据 | - |

**🔥 重点说明：**
- 会话状态：`in_progress`（进行中）、`completed`（已完成）、`abandoned`（已放弃）
- 批量创建答题记录会先删除旧记录，避免重复数据
- 答题卡序号从 1 开始

---

## 3. 题库与章节模块

| 接口地址 | 方法 | 功能说明 | 关键参数 |
|---------|------|---------|---------|
| `/api/v1/qbank/banks` | GET | 获取题库列表 | - |
| `/api/v1/qbank/banks/{bank_id}` | GET | 获取题库详情（含章节列表） | - |
| `/api/v1/qbank/chapters/{chapter_id}` | GET | 获取章节详情 | - |

---

## 4. 收藏与笔记模块

| 接口地址 | 方法 | 功能说明 | 关键参数 |
|---------|------|---------|---------|
| `/api/v1/qbank/favorites/toggle` | POST | 切换收藏状态（收藏/取消收藏） | `question_id` |
| `/api/v1/qbank/favorites/check` | POST | 批量检查题目是否已收藏 | `question_ids[]` |
| `/api/v1/qbank/favorites` | GET | 获取收藏列表 | `page`, `size`, `bank_id`, `type` |

---

## 5. 核心业务流程

### 5.1 开始新练习

```
1. GET  /api/v1/qbank/banks/{bank_id}                        → 获取题库信息
2. GET  /api/v1/qbank/practice/banks/{bank_id}/questions     → 获取题目列表（不含答案）
3. POST /api/v1/qbank/practice/sessions                      → 创建练习会话
4. POST /api/v1/qbank/practice/records                       → 答题时实时保存记录
5. PUT  /api/v1/qbank/practice/sessions/{session_id}         → 更新会话统计
6. POST /api/v1/qbank/practice/submit                        → 批量提交答案
7. POST /api/v1/qbank/practice/records/batch                 → 批量保存答题记录
8. POST /api/v1/qbank/practice/sessions/{session_id}/submit  → 提交练习会话
```

### 5.2 继续未完成的练习

```
1. GET /api/v1/qbank/practice/sessions/{session_id}          → 获取会话详情
2. GET /api/v1/qbank/questions?ids=1,2,3                     → 获取题目列表
3. GET /api/v1/qbank/practice/sessions/{session_id}/records  → 获取已有答题记录
4. 恢复答题状态，从未答题目继续...
```

### 5.3 查看历史记录 🔥

```
1. GET /api/v1/qbank/practice/sessions/{session_id}                    → 获取会话详情（question_ids）
2. GET /api/v1/qbank/questions?ids=1,2,3&include_answer=true           → 获取最新题目+答案+解析
3. GET /api/v1/qbank/practice/sessions/{session_id}/records            → 获取历史答题记录
4. 前端组合：最新题目 + 历史答案 → 重新判分 → 展示结果
```

**优势：**
- ✅ 不存储题目快照，节省存储空间
- ✅ 历史记录永远显示最新版本的题目
- ✅ 题目修改后，历史记录也能受益

---

## 6. 数据格式规范

### 6.1 题目类型 (type)
```
single        # 单选题
multiple      # 多选题
judgement     # 判断题
fill_blank    # 填空题
short_answer  # 简答题
```

### 6.2 难度等级 (difficulty)
```
easy    # 简单
medium  # 中等
hard    # 困难
```

### 6.3 会话状态 (status)
```
in_progress  # 进行中
completed    # 已完成
abandoned    # 已放弃
```

### 6.4 会话类型 (session_type)
```
bank      # 题库练习
chapter   # 章节练习
random    # 随机练习
exam      # 模拟考试
wrong     # 错题练习
favorite  # 收藏练习
```

### 6.5 答案格式

**API 提交格式：**
- 单选：`"A"`
- 多选：`"A,B,C"`（英文逗号分隔）
- 判断：`"true"` / `"false"`
- 填空/简答：`"答案内容"`

**数据库存储格式：**
```json
{
  "correct": ["A"],           // 单选
  "correct": ["A", "B", "C"], // 多选
  "correct": ["true"],        // 判断
  "correct": ["答案内容"]      // 填空/简答
}
```

### 6.6 答题卡状态 (status)
```
unselected  # 未作答
selected    # 已选择但未提交（刷题模式）
correct     # 答对
wrong       # 答错
```

---

## 7. 关键技术要点

### 7.1 答案格式统一化
- 后端判分前统一转换：`"A，B"` → `["A", "B"]`
- 排序后比较，避免顺序问题

### 7.2 查看历史记录的重新判分机制
- 不存储题目快照，只存用户答案
- 查看历史时：获取最新题目 + 历史答案 → 前端重新判分

### 7.3 答题记录去重
- 批量创建答题记录前，先删除该会话的所有旧记录
- 避免实时保存 + 批量保存产生重复数据

### 7.4 条件加载优化
- `include_analysis=true` 时才加载题目解析关系
- 减少不必要的数据库查询

### 7.5 答题卡序号修复
- 答题卡序号从 1 开始（已修复之前从 0 开始的问题）

---

## 8. 改进建议

| 优化方向 | 具体方案 |
|---------|---------|
| 缓存优化 | 题目列表、题库信息添加 Redis 缓存 |
| 批量操作 | 收藏状态批量查询优化为单次 SQL |
| 异步化 | 题目统计更新使用消息队列 |
| 接口版本化 | 添加 `/v2/` 版本前缀 |
| 数据迁移 | 添加 `question_version` 字段追踪版本 |

---

**文档版本：** v1.0
**更新时间：** 2025-12-13
**维护人员：** 题库系统开发组
