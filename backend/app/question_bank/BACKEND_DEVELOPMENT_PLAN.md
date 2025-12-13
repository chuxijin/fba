# 题库小程序后端完善方案

## 一、现有架构分析

### ✅ 已完成的模块

#### 1. **核心数据模型** (model/)
- ✅ `UserAccount`: 用户账户（包含微信登录、个人信息）
- ✅ `ExamCategory`: 题库分类
- ✅ `QuestionBank`: 题库
- ✅ `QuestionChapter`: 章节
- ✅ `Question`: 题目
- ✅ `QuestionAnalysis`: 题目解析
- ✅ `QuestionStatistics`: 题目统计
- ✅ `PracticeSession`: 练习会话
- ✅ `PracticeRecord`: 答题记录
- ✅ `WrongQuestionBook`: 错题本
- ✅ `QuestionNote`: 笔记
- ✅ `QuestionFavorite`: 收藏
- ✅ `UserMembership`: 会员权益
- ✅ `UserGrowthPoints`: 成长积分
- ✅ `SpreadRelation`: 推广关系
- ✅ `UserCommission`: 用户佣金

#### 2. **API 路由** (api/v1/)
- ✅ `/auth` - 认证
- ✅ `/customer` - 用户
- ✅ `/categories` - 分类
- ✅ `/banks` - 题库
- ✅ `/chapters` - 章节
- ✅ `/questions` - 题目
- ✅ `/memberships` - 会员
- ✅ `/practice` - 练习
- ✅ `/sessions` - 练习会话
- ✅ `/wrong-questions` - 错题
- ✅ `/notes` - 笔记
- ✅ `/favorites` - 收藏
- ✅ `/upload` - 上传

---

## 二、前后端对接清单

### 1. **用户认证流程**

#### 前端需求：
```typescript
// miniprogram/api/business/auth.ts
POST /api/v1/qbank/auth/wechat-login
{
  code: string        // 微信登录凭证
  encryptedData?: string
  iv?: string
}

Response:
{
  access_token: string
  user_info: {
    id: number
    nickname: string
    avatar: string
    is_vip: boolean
  }
}
```

#### 后端状态：
- ✅ 路由已存在：`api/v1/auth.py`
- ⚠️ 需要检查：微信解密逻辑是否完整
- ⚠️ 需要补充：用户信息返回格式是否匹配

#### 行动计划：
1. 检查 `auth_service.py` 中的微信登录逻辑
2. 补充用户信息格式化 Schema
3. 测试微信登录完整流程

---

### 2. **题库分类获取**

#### 前端需求：
```typescript
// miniprogram/api/business/category.ts
GET /api/v1/qbank/categories/tree?cat_type=1&is_active=true

Response:
[
  {
    id: number
    name: string
    icon?: string
    cat_type: number
    is_active: boolean
    sort_order: number
    children: Category[]
  }
]
```

#### 后端状态：
- ✅ 路由已存在：`api/v1/category.py`
- ✅ Service 已存在：`category_service.py`
- ⚠️ 需要确认：返回格式是否包含树形结构

#### 行动计划：
1. 检查 `getCategoryTree` 接口返回格式
2. 确保支持 `cat_type` 和 `is_active` 筛选
3. 测试树形结构构建逻辑

---

### 3. **题库列表获取**

#### 前端需求：
```typescript
// miniprogram/api/business/bank.ts
GET /api/v1/qbank/banks?status=1&cat_id=1

Response:
[
  {
    id: number
    name: string
    cover_url?: string
    cat_id: number
    scope: number      // 权限范围
    status: number
    q_count: number    // 题目数量
    buy_count: number  // 购买人数
    parent_id?: number
    children?: Bank[]
  }
]
```

#### 后端状态：
- ✅ 路由已存在：`api/v1/bank.py`
- ⚠️ 需要确认：是否支持树形结构返回
- ⚠️ 需要补充：权限判断逻辑

#### 行动计划：
1. 检查题库列表接口是否支持父子关系
2. 添加用户权限判断逻辑（VIP、购买、免费）
3. 补充题目数量统计字段

---

### 4. **章节列表获取**

#### 前端需求：
```typescript
// miniprogram/api/business/chapter.ts
GET /api/v1/qbank/chapters/tree?bank_id=1

Response:
[
  {
    id: number
    name: string
    bank_id: number
    is_trial: boolean  // 是否试用章节
    q_count: number
    sort_order: number
  }
]
```

#### 后端状态：
- ✅ 路由已存在：`api/v1/chapter.py`
- ⚠️ 需要确认：`is_trial` 字段是否存在

#### 行动计划：
1. 检查章节模型是否有 `is_trial` 字段
2. 如果没有，添加到模型和 Schema
3. 测试章节树形结构返回

---

### 5. **开始练习（创建会话）**

#### 前端需求：
```typescript
// miniprogram/api/business/practice.ts
POST /api/v1/qbank/practice/sessions
{
  session_type: 'chapter' | 'bank' | 'random' | 'wrong' | 'favorite'
  bank_id?: number
  chapter_id?: number
  question_count?: number
}

Response:
{
  session_id: number
  questions: [
    {
      id: number
      type: string
      content: string
      options?: string[]
      // ... 其他题目字段
    }
  ]
}
```

#### 后端状态：
- ✅ 模型已存在：`PracticeSession`
- ⚠️ 需要确认：创建会话接口逻辑
- ⚠️ 需要补充：题目获取逻辑（随机/顺序）

#### 行动计划：
1. 实现创建会话接口
2. 实现题目筛选逻辑（章节/题库/随机）
3. 返回题目列表（不包含答案）

---

### 6. **提交答案**

#### 前端需求：
```typescript
POST /api/v1/qbank/practice/sessions/{session_id}/answer
{
  question_id: number
  user_answer: string | string[]  // 单选/多选
  time_spent: number  // 答题耗时（秒）
}

Response:
{
  is_correct: boolean
  correct_answer: string | string[]
  analysis?: string
  user_statistics: {
    total: number
    correct: number
    accuracy: number
  }
}
```

#### 后端状态：
- ✅ 模型已存在：`PracticeRecord`
- ⚠️ 需要实现：提交答案接口
- ⚠️ 需要补充：实时统计更新逻辑

#### 行动计划：
1. 实现提交答案接口
2. 判断答案正误
3. 更新 Session 统计数据（completed_count, correct_count, accuracy_rate）
4. 错题自动加入错题本
5. 返回正确答案和解析

---

### 7. **获取练习进度**

#### 前端需求：
```typescript
GET /api/v1/qbank/practice/progress?bank_id=1

Response:
{
  bank_id: number
  total_questions: number
  completed_questions: number
  accuracy_rate: number
  last_practice_time: string
}
```

#### 后端状态：
- ⚠️ 需要实现：进度统计接口
- ⚠️ 需要设计：统计数据缓存策略

#### 行动计划：
1. 实现用户进度查询接口
2. 统计指定题库/章节的完成情况
3. 添加 Redis 缓存提升性能

---

### 8. **错题本管理**

#### 前端需求：
```typescript
// 获取错题列表
GET /api/v1/qbank/wrong-questions?bank_id=1

// 移除错题
DELETE /api/v1/qbank/wrong-questions/{id}
```

#### 后端状态：
- ✅ 路由已存在：`api/v1/wrong_question.py`
- ⚠️ 需要确认：CRUD 逻辑是否完整

#### 行动计划：
1. 检查错题 CRUD 接口
2. 添加按题库/章节筛选功能
3. 支持批量删除

---

### 9. **收藏管理**

#### 前端需求：
```typescript
// 收藏题目
POST /api/v1/qbank/favorites
{ question_id: number }

// 取消收藏
DELETE /api/v1/qbank/favorites/{question_id}

// 获取收藏列表
GET /api/v1/qbank/favorites?bank_id=1
```

#### 后端状态：
- ✅ 路由已存在：`api/v1/favorite.py`
- ⚠️ 需要确认：CRUD 逻辑是否完整

#### 行动计划：
1. 检查收藏 CRUD 接口
2. 支持按题库筛选
3. 返回收藏的题目详情

---

### 10. **笔记管理**

#### 前端需求：
```typescript
// 添加笔记
POST /api/v1/qbank/notes
{
  question_id: number
  content: string
}

// 更新笔记
PUT /api/v1/qbank/notes/{id}
{ content: string }

// 获取笔记列表
GET /api/v1/qbank/notes?question_id=1
```

#### 后端状态：
- ✅ 路由已存在：`api/v1/note.py`
- ⚠️ 需要确认：CRUD 逻辑是否完整

#### 行动计划：
1. 检查笔记 CRUD 接口
2. 支持笔记点赞功能（UserNoteVote）
3. 支持查看其他用户优质笔记

---

### 11. **会员权益查询**

#### 前端需求：
```typescript
GET /api/v1/qbank/customer/memberships

Response:
{
  is_vip: boolean
  vip_type: 'all' | 'category' | 'bank'
  expire_time?: string
  category_ids?: number[]  // 分类会员
  bank_ids?: number[]      // 题库会员
}
```

#### 后端状态：
- ✅ 模型已存在：`UserMembership`
- ⚠️ 需要实现：会员权益查询接口
- ⚠️ 需要补充：权限判断逻辑

#### 行动计划：
1. 实现会员信息查询接口
2. 返回用户所有有效会员权益
3. 提供权限判断工具函数

---

## 三、核心功能优先级

### 🔥 P0（最高优先级 - 核心功能）

1. **微信登录** - 用户必须登录才能使用
   - `POST /api/v1/qbank/auth/wechat-login`
   - 验证、检查现有逻辑

2. **题库列表** - 用户选择题库的入口
   - `GET /api/v1/qbank/banks`
   - 确保返回格式正确、包含权限判断

3. **章节列表** - 用户选择章节练习
   - `GET /api/v1/qbank/chapters/tree`
   - 确保支持试用章节标记

4. **创建练习会话** - 开始刷题的核心
   - `POST /api/v1/qbank/practice/sessions`
   - 实现题目筛选逻辑

5. **提交答案** - 刷题核心交互
   - `POST /api/v1/qbank/practice/sessions/{id}/answer`
   - 判断对错、更新统计、加入错题本

6. **获取用户进度** - 展示学习进度
   - `GET /api/v1/qbank/practice/progress`
   - 统计完成题数、正确率

### ⭐ P1（高优先级 - 重要功能）

7. **会员权益查询** - 判断用户能否访问题库
   - `GET /api/v1/qbank/customer/memberships`
   - 返回所有有效会员信息

8. **错题本** - 用户复习错题
   - `GET /api/v1/qbank/wrong-questions`
   - 支持按题库筛选

9. **收藏功能** - 用户收藏重点题目
   - CRUD 接口检查

### 🎯 P2（中优先级 - 增值功能）

10. **笔记功能** - 用户记录学习心得
    - CRUD 接口检查
    - 笔记点赞功能

11. **学习统计** - 展示学习数据
    - 每日刷题统计
    - 知识点掌握情况

12. **分享功能** - 邀请好友
    - 生成分享海报
    - 记录推广关系

---

## 四、数据库补充建议

### 需要添加的字段

#### 1. **QuestionChapter 表**
```sql
ALTER TABLE study_question_chapter
ADD COLUMN is_trial BOOLEAN DEFAULT FALSE COMMENT '是否试用章节';
```

#### 2. **QuestionBank 表**
```sql
-- 如果没有题目数量字段，添加
ALTER TABLE study_question_bank
ADD COLUMN q_count INT DEFAULT 0 COMMENT '题目数量（冗余字段，提升性能）';

-- 如果没有购买人数字段，添加
ALTER TABLE study_question_bank
ADD COLUMN buy_count INT DEFAULT 0 COMMENT '购买人数（虚拟/真实）';
```

#### 3. **UserAccount 表**
```sql
-- 检查是否有最近学习时间
ALTER TABLE study_user_account
ADD COLUMN last_study_time TIMESTAMP NULL COMMENT '最近学习时间';

-- 检查是否有连续学习天数
ALTER TABLE study_user_account
ADD COLUMN continuous_study_days INT DEFAULT 0 COMMENT '连续学习天数';
```

---

## 五、开发顺序建议

### 第一阶段：核心刷题流程（2-3天）

```
Day 1: 认证 + 题库列表
├── 1. 测试微信登录接口
├── 2. 完善题库列表返回格式
├── 3. 添加权限判断逻辑
└── 4. 前后端联调测试

Day 2: 章节 + 开始练习
├── 1. 完善章节列表接口
├── 2. 实现创建练习会话
├── 3. 实现题目筛选逻辑
└── 4. 前后端联调测试

Day 3: 提交答案 + 进度统计
├── 1. 实现提交答案接口
├── 2. 实现判题逻辑
├── 3. 实现进度统计接口
├── 4. 错题自动加入错题本
└── 5. 前后端联调测试
```

### 第二阶段：会员 + 错题收藏（1-2天）

```
Day 4: 会员权益
├── 1. 实现会员查询接口
├── 2. 添加权限判断逻辑
├── 3. 前端对接权限展示
└── 4. 测试不同会员权限

Day 5: 错题 + 收藏 + 笔记
├── 1. 完善错题本接口
├── 2. 完善收藏接口
├── 3. 完善笔记接口
└── 4. 前后端联调测试
```

### 第三阶段：优化 + 增值功能（2-3天）

```
Day 6-7: 性能优化
├── 1. 添加 Redis 缓存（题库列表、用户进度）
├── 2. 优化 SQL 查询（索引、N+1 问题）
├── 3. 添加接口限流
└── 4. 压力测试

Day 8: 增值功能
├── 1. 学习统计数据
├── 2. 打卡功能
├── 3. 分享邀请
└── 4. 推送通知
```

---

## 六、关键技术点

### 1. **权限判断逻辑**

```python
# backend/app/question_bank/security.py
def check_bank_access(user: UserAccount, bank: QuestionBank) -> dict:
    """
    检查用户对题库的访问权限

    :param user: 用户对象
    :param bank: 题库对象
    :return: {"has_access": bool, "reason": str}
    """
    # 1. 免费题库：所有人可访问
    if bank.scope == 0:
        return {"has_access": True, "reason": "free"}

    # 2. VIP 全站会员
    if user.is_vip:
        membership = get_valid_vip_membership(user.id, 'all')
        if membership:
            return {
                "has_access": True,
                "reason": "vip_all",
                "end_time": membership.end_time,
                "remaining_days": (membership.end_time - datetime.now()).days
            }

    # 3. 分类会员
    cat_membership = get_valid_category_membership(user.id, bank.cat_id)
    if cat_membership:
        return {"has_access": True, "reason": "vip_category"}

    # 4. 单独购买
    bank_purchase = get_bank_purchase(user.id, bank.id)
    if bank_purchase:
        return {"has_access": True, "reason": "purchased"}

    # 5. 无权限
    return {"has_access": False, "reason": "locked"}
```

### 2. **练习会话管理**

```python
# backend/app/question_bank/service/practice_service.py
async def create_practice_session(
    user_id: int,
    session_type: str,
    bank_id: int | None = None,
    chapter_id: int | None = None,
    question_count: int = 20
) -> dict:
    """
    创建练习会话

    :param user_id: 用户 ID
    :param session_type: 会话类型
    :param bank_id: 题库 ID
    :param chapter_id: 章节 ID
    :param question_count: 题目数量
    :return: 会话信息 + 题目列表
    """
    # 1. 筛选题目
    questions = await get_questions_for_session(
        session_type, bank_id, chapter_id, question_count, user_id
    )

    # 2. 创建会话
    session = PracticeSession(
        user_id=user_id,
        session_type=session_type,
        bank_id=bank_id,
        chapter_id=chapter_id,
        question_ids=[q.id for q in questions],
        total_count=len(questions)
    )
    await session_crud.create(session)

    # 3. 返回（不包含答案）
    return {
        "session_id": session.id,
        "questions": [format_question_for_practice(q) for q in questions]
    }
```

### 3. **判题逻辑**

```python
async def submit_answer(
    session_id: int,
    question_id: int,
    user_answer: str | list[str],
    time_spent: int
) -> dict:
    """
    提交答案并判题
    """
    # 1. 获取题目和正确答案
    question = await question_crud.get(question_id)
    correct_answer = question.correct_answer

    # 2. 判断对错
    is_correct = check_answer_correctness(user_answer, correct_answer, question.type)

    # 3. 创建答题记录
    record = PracticeRecord(
        session_id=session_id,
        question_id=question_id,
        user_answer=user_answer,
        is_correct=is_correct,
        time_spent=time_spent
    )
    await record_crud.create(record)

    # 4. 更新会话统计
    session = await session_crud.get(session_id)
    session.completed_count += 1
    if is_correct:
        session.correct_count += 1
    else:
        session.wrong_count += 1
        # 加入错题本
        await add_to_wrong_book(session.user_id, question_id)

    session.accuracy_rate = (session.correct_count / session.completed_count) * 100
    await session_crud.update(session)

    # 5. 返回结果
    return {
        "is_correct": is_correct,
        "correct_answer": correct_answer,
        "analysis": question.analysis.content if question.analysis else None,
        "user_statistics": {
            "total": session.completed_count,
            "correct": session.correct_count,
            "accuracy": float(session.accuracy_rate)
        }
    }
```

---

## 七、前后端联调检查清单

### 联调前准备

- [ ] 后端接口文档已生成（Swagger/Redoc）
- [ ] 所有接口都有清晰的请求/响应示例
- [ ] 错误码统一规范
- [ ] 开发环境数据库已初始化测试数据

### 接口联调顺序

1. [ ] 微信登录 → 获取 token
2. [ ] 获取题库分类 → 展示分类列表
3. [ ] 获取题库列表 → 展示题库卡片
4. [ ] 获取章节列表 → 展示章节列表
5. [ ] 创建练习会话 → 开始刷题
6. [ ] 提交答案 → 显示对错
7. [ ] 获取用户进度 → 展示进度条
8. [ ] 错题本/收藏/笔记 → CRUD 功能

### 性能测试

- [ ] 题库列表加载时间 < 500ms
- [ ] 创建会话（获取题目）< 1s
- [ ] 提交答案响应时间 < 300ms
- [ ] 支持 100 并发用户

---

## 八、下一步行动

### 立即开始

1. **检查现有接口**
   ```bash
   # 启动后端服务
   uvicorn backend.main:app --reload

   # 访问 API 文档
   http://localhost:8000/docs
   ```

2. **逐个测试 P0 接口**
   - 微信登录
   - 题库列表
   - 章节列表
   - 创建会话
   - 提交答案
   - 用户进度

3. **记录问题清单**
   - 哪些接口缺失
   - 哪些字段不匹配
   - 哪些逻辑需要补充

4. **按优先级修复**
   - P0 功能必须全部完成
   - P1 功能尽量完成
   - P2 功能可后续迭代

---

**文档维护**: 2025-12-09
**负责人**: 开发团队
**预计完成时间**: 5-7 个工作日
