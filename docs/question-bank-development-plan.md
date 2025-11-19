# 微信刷题小程序开发计划

> **项目名称**: 微信刷题小程序
> **开发模式**: 独立开发
> **目标时间**: 4-6 周
> **文档更新**: 2024-11-17

---

## 📊 当前进度总览

### 整体进度: 60% ✅

| 模块 | 完成度 | 状态 |
|------|--------|------|
| 后端 API | 70% | 🟢 核心完成 |
| 管理后台 | 80% | 🟢 可用 |
| 小程序 | 40% | 🟡 进行中 |

---

## ✅ 已完成功能清单

### 后端 (backend/app/question_bank)

- [x] 数据模型设计
  - [x] QuestionBank - 题库表
  - [x] QuestionCategory - 分类表
  - [x] QuestionChapter - 章节表
  - [x] Question - 题目表
  - [x] QuestionAnalysis - 解析表
  - [x] QuestionStatistics - 统计表
  - [x] QuestionBankUser - 用户表
  - [x] UserMembership - 会员表

- [x] 题库管理 API
  - [x] GET /api/v1/question-bank/banks - 获取题库列表
  - [x] POST /api/v1/question-bank/banks - 创建题库
  - [x] PUT /api/v1/question-bank/banks/{id} - 更新题库
  - [x] DELETE /api/v1/question-bank/banks - 删除题库

- [x] 题目管理 API
  - [x] GET /api/v1/question-bank/questions - 获取题目列表
  - [x] GET /api/v1/question-bank/questions/{id} - 获取题目详情
  - [x] POST /api/v1/question-bank/questions - 创建题目
  - [x] PUT /api/v1/question-bank/questions/{id} - 更新题目
  - [x] DELETE /api/v1/question-bank/questions - 删除题目

- [x] 解析管理 API
  - [x] GET /api/v1/question-bank/questions/{id}/analysis - 获取解析
  - [x] POST /api/v1/question-bank/questions/{id}/analysis - 创建解析
  - [x] PUT /api/v1/question-bank/questions/{id}/analysis - 更新解析
  - [x] POST /api/v1/question-bank/questions/{id}/analysis/helpful - 标记有帮助

- [x] 刷题专用 API
  - [x] GET /api/v1/question-bank/practice/questions - 获取练习题目
  - [x] GET /api/v1/question-bank/practice/questions/{id} - 获取题目详情
  - [x] GET /api/v1/question-bank/practice/questions/{id}/analysis - 查看解析
  - [x] POST /api/v1/question-bank/practice/submit - 批量提交答案

- [x] 权限验证
  - [x] 会员权限验证
  - [x] 题库访问验证
  - [x] 章节访问验证

### 前端后台 (frontend/apps/web-antd/src/views/knowledge-store)

- [x] 题库管理
  - [x] 题库列表页面
  - [x] 题库新增/编辑表单
  - [x] 题库基本信息维护
  - [x] 封面上传

- [x] 题目管理
  - [x] 题目列表页面
  - [x] 题目新增/编辑表单
  - [x] 支持 5 种题型
    - [x] 单选题
    - [x] 多选题
    - [x] 判断题
    - [x] 填空题
    - [x] 简答题
  - [x] Markdown 富文本编辑器
  - [x] 图片上传功能
  - [x] 题目导入功能

- [x] 章节管理
  - [x] 章节列表
  - [x] 章节新增/编辑
  - [x] 章节排序

- [x] 分类管理
  - [x] 分类列表
  - [x] 分类维护

### 小程序 (miniprogram/pages)

- [x] 刷题核心功能
  - [x] 练习页面 (pages/practice/index.vue)
  - [x] 题目卡片组件
  - [x] 解析面板组件
  - [x] 答题卡组件
  - [x] 滑动切题功能
  - [x] 答题确认功能

- [x] 基础框架
  - [x] 首页框架 (pages/index/index.vue)
  - [x] 我的页面框架 (pages/mine/index.vue)

---

## 📋 待开发功能清单

### Week 1: 核心闭环（MVP）

**目标**: 小程序能完整跑通"登录 → 选题库 → 刷题 → 查看记录"

#### 后端开发

- [ ] **答题记录模块** (2-3 天)
  - [ ] 创建数据模型 `backend/app/question_bank/model/practice_record.py`
    ```python
    class PracticeRecord(Base, UserMixin):
        user_id: int
        question_id: int
        user_answer: str | list[str]
        is_correct: bool
        answer_time: int  # 答题时长(秒)
        created_time: datetime
    ```
  - [ ] 创建 CRUD `backend/app/question_bank/crud/crud_practice_record.py`
  - [ ] 创建 Schema `backend/app/question_bank/schema/practice_record.py`
  - [ ] 创建 API `backend/app/question_bank/api/v1/record.py`
    - [ ] POST /practice/records - 提交答题记录
    - [ ] GET /practice/records - 查询答题记录
    - [ ] GET /practice/records/latest - 获取最近记录

- [ ] **用户统计模块** (1-2 天)
  - [ ] 创建数据模型 `backend/app/question_bank/model/user_statistics.py`
    ```python
    class UserStatistics(Base):
        user_id: int
        total_questions: int       # 总做题数
        correct_count: int         # 正确数
        total_time: int           # 总时长(秒)
        bank_stats: dict          # 各题库统计(JSON)
        last_practice_time: datetime
    ```
  - [ ] 创建 Service `backend/app/question_bank/service/statistics_service.py`
  - [ ] 创建 API
    - [ ] GET /practice/statistics - 获取用户统计
    - [ ] GET /practice/statistics/daily - 每日统计

#### 小程序开发

- [ ] **登录页面** (1 天) `miniprogram/pages/login/index.vue`
  - [ ] 微信授权登录按钮
  - [ ] 调用微信登录 API
  - [ ] 获取并存储 Token
  - [ ] 用户信息存储
  - [ ] 登录成功跳转

- [ ] **题库列表页** (1 天) `miniprogram/pages/bank-list/index.vue`
  - [ ] 题库列表展示
  - [ ] 题库卡片设计
    - [ ] 题库名称
    - [ ] 封面图片
    - [ ] 题目数量
    - [ ] 已做题数
  - [ ] 点击进入章节列表
  - [ ] 下拉刷新
  - [ ] 加载更多

- [ ] **章节列表页** (1 天) `miniprogram/pages/chapter-list/index.vue`
  - [ ] 章节列表展示
  - [ ] 章节卡片设计
    - [ ] 章节名称
    - [ ] 题目数量
    - [ ] 完成进度
  - [ ] 开始练习按钮
  - [ ] 顺序练习/随机练习选择

- [ ] **完善首页** (1 天) `miniprogram/pages/index/index.vue`
  - [ ] 顶部欢迎区域
  - [ ] 今日学习统计卡片
  - [ ] 最近练习题库
  - [ ] 快捷入口（错题本、收藏、统计）
  - [ ] 继续上次练习功能

**Week 1 交付物**: ✅ 能完整体验登录→选题库→刷题→查看记录

---

### Week 2: 错题本 + 收藏功能

**目标**: 用户能收藏题目、查看错题

#### 后端开发

- [ ] **错题本模块** (1 天)
  - [ ] 创建数据模型 `backend/app/question_bank/model/wrong_question_book.py`
    ```python
    class WrongQuestionBook(Base, UserMixin):
        user_id: int
        question_id: int
        wrong_count: int          # 错误次数
        last_wrong_time: datetime
        is_mastered: bool         # 是否已掌握
    ```
  - [ ] 创建 API `backend/app/question_bank/api/v1/wrong_question.py`
    - [ ] GET /practice/wrong-questions - 获取错题列表
    - [ ] POST /practice/wrong-questions/{id}/master - 标记已掌握
    - [ ] DELETE /practice/wrong-questions/{id} - 移出错题本

- [ ] **收藏模块** (1 天)
  - [ ] 创建数据模型 `backend/app/question_bank/model/question_favorite.py`
    ```python
    class QuestionFavorite(Base, UserMixin):
        user_id: int
        question_id: int
        created_time: datetime
    ```
  - [ ] 创建 API `backend/app/question_bank/api/v1/favorite.py`
    - [ ] POST /practice/favorites - 收藏题目
    - [ ] DELETE /practice/favorites/{id} - 取消收藏
    - [ ] GET /practice/favorites - 获取收藏列表

#### 小程序开发

- [ ] **错题本页面** (1.5 天) `miniprogram/pages/wrong-book/index.vue`
  - [ ] 错题列表展示
  - [ ] 按题库筛选
  - [ ] 按章节筛选
  - [ ] 显示错误次数
  - [ ] 标记已掌握按钮
  - [ ] 一键开始错题练习
  - [ ] 清空已掌握题目

- [ ] **收藏页面** (1 天) `miniprogram/pages/favorites/index.vue`
  - [ ] 收藏列表展示
  - [ ] 取消收藏操作
  - [ ] 批量取消收藏
  - [ ] 开始收藏题练习

- [ ] **完善"我的"页面** (0.5 天) `miniprogram/pages/mine/index.vue`
  - [ ] 用户头像和昵称
  - [ ] 学习统计卡片（做题数、正确率、学习天数）
  - [ ] 功能入口列表
    - [ ] 错题本（带数量角标）
    - [ ] 收藏（带数量角标）
    - [ ] 学习统计
    - [ ] 设置

**Week 2 交付物**: ✅ 错题本和收藏功能可用

---

### Week 3: 统计 & 数据可视化

**目标**: 用户能看到详细的学习数据

#### 后端开发

- [ ] **统计 API 增强** (1-2 天)
  - [ ] GET /practice/statistics/daily - 每日学习数据
    - [ ] 支持 7 天/30 天
    - [ ] 返回：日期、做题数、正确率、学习时长
  - [ ] GET /practice/statistics/accuracy-trend - 正确率趋势
  - [ ] GET /practice/statistics/weak-points - 薄弱知识点分析
  - [ ] GET /practice/statistics/question-type - 各题型统计

#### 小程序开发

- [ ] **统计页面** (2-3 天) `miniprogram/pages/statistics/index.vue`
  - [ ] 顶部统计卡片
    - [ ] 累计学习天数
    - [ ] 累计做题数
    - [ ] 平均正确率
    - [ ] 累计学习时长
  - [ ] 学习时长趋势图（7天/30天）
  - [ ] 正确率趋势图
  - [ ] 题型分布饼图
  - [ ] 薄弱知识点列表
  - [ ] 各题库练习进度

- [ ] **打卡功能** (1 天)
  - [ ] 每日打卡记录
  - [ ] 打卡日历组件
  - [ ] 连续打卡天数
  - [ ] 打卡提醒

**Week 3 交付物**: ✅ 用户能看到详细的学习数据和可视化图表

---

### Week 4: 笔记功能 + 全面优化

**目标**: 笔记功能 + 性能和体验优化

#### 后端开发

- [ ] **笔记模块** (1 天)
  - [ ] 创建数据模型 `backend/app/question_bank/model/question_note.py`
    ```python
    class QuestionNote(Base, UserMixin):
        user_id: int
        question_id: int
        content: str
        created_time: datetime
        updated_time: datetime
    ```
  - [ ] 创建 API `backend/app/question_bank/api/v1/note.py`
    - [ ] POST /practice/notes - 添加笔记
    - [ ] PUT /practice/notes/{id} - 更新笔记
    - [ ] DELETE /practice/notes/{id} - 删除笔记
    - [ ] GET /practice/questions/{id}/note - 获取题目笔记
    - [ ] GET /practice/notes - 获取我的笔记列表

#### 小程序开发

- [ ] **笔记功能** (1-2 天)
  - [ ] 练习页面添加笔记入口
  - [ ] 笔记弹窗组件 `miniprogram/components/NoteModal.vue`
  - [ ] 笔记列表页面 `miniprogram/pages/notes/index.vue`
  - [ ] 笔记编辑器
  - [ ] 笔记查看和管理

#### 全端优化

- [ ] **性能优化** (1 天)
  - [ ] 图片懒加载
  - [ ] 题目列表虚拟滚动
  - [ ] API 响应缓存
  - [ ] 减少不必要的请求
  - [ ] 优化包体积

- [ ] **用户体验优化** (1 天)
  - [ ] 添加骨架屏
  - [ ] 优化加载动画
  - [ ] 错误提示优化
  - [ ] 操作反馈优化
  - [ ] 按钮防抖

**Week 4 交付物**: ✅ 笔记功能完成，整体性能和体验显著提升

---

### Week 5-6: 后台管理补充 + 内测 + 上线准备

**目标**: 补充后台功能，内测修 Bug，准备上线

#### 后台管理补充

- [ ] **用户管理增强** (1 天)
  - [ ] 用户列表页面
  - [ ] 用户详情查看
  - [ ] 用户答题记录查看
  - [ ] 用户统计数据展示
  - [ ] 用户行为分析

- [ ] **统计 Dashboard** (1-2 天)
  - [ ] 总览数据卡片
  - [ ] 题库使用量统计
  - [ ] 题目答题统计
  - [ ] 用户活跃度统计
  - [ ] 数据导出功能

#### 内测阶段

- [ ] **内测准备** (1 天)
  - [ ] 邀请 5-10 人内测
  - [ ] 准备内测指南
  - [ ] 收集反馈渠道（问卷/群聊）

- [ ] **Bug 修复** (3-4 天)
  - [ ] 收集并分类 Bug
  - [ ] 修复高优先级 Bug
  - [ ] 修复中优先级 Bug
  - [ ] 验证修复效果

- [ ] **优化迭代** (2-3 天)
  - [ ] 根据反馈优化 UI/UX
  - [ ] 性能进一步优化
  - [ ] 补充遗漏功能

#### 上线准备

- [ ] **题库内容** (持续)
  - [ ] 累计录入 300+ 题目
  - [ ] 至少覆盖 2-3 个题库
  - [ ] 题目质量审核

- [ ] **小程序提审** (2-3 天)
  - [ ] 隐私政策页面
  - [ ] 用户协议页面
  - [ ] 功能说明
  - [ ] 提审资料准备
  - [ ] 提交审核

- [ ] **服务器部署** (1 天)
  - [ ] 生产环境部署
  - [ ] 配置域名和 SSL
  - [ ] 配置监控和日志
  - [ ] 配置备份策略

**Week 5-6 交付物**: ✅ 小程序审核通过，正式上线

---

## 📅 时间线

```
Week 1 (11.18 - 11.24): 核心闭环
├── 11.18-11.20: 后端答题记录+统计
├── 11.21-11.22: 小程序登录+题库列表
├── 11.23-11.24: 小程序章节列表+首页完善
└── 里程碑: ✅ 完整刷题流程可用

Week 2 (11.25 - 12.01): 错题本+收藏
├── 11.25-11.26: 后端错题本+收藏模块
├── 11.27-11.29: 小程序错题本+收藏页面
├── 11.30-12.01: 完善"我的"页面
└── 里程碑: ✅ 错题本和收藏可用

Week 3 (12.02 - 12.08): 统计可视化
├── 12.02-12.03: 后端统计 API 增强
├── 12.04-12.06: 小程序统计页面
├── 12.07-12.08: 打卡功能
└── 里程碑: ✅ 数据统计完整

Week 4 (12.09 - 12.15): 笔记+优化
├── 12.09-12.10: 后端笔记模块
├── 12.11-12.12: 小程序笔记功能
├── 12.13-12.14: 性能优化
├── 12.15: 用户体验优化
└── 里程碑: ✅ 功能完善，可内测

Week 5 (12.16 - 12.22): 后台+内测
├── 12.16-12.17: 后台管理补充
├── 12.18-12.22: 内测+Bug 修复
└── 里程碑: ✅ 内测版本稳定

Week 6 (12.23 - 12.29): 上线准备
├── 12.23-12.25: 优化迭代
├── 12.26-12.27: 提审准备
├── 12.28-12.29: 服务器部署
└── 里程碑: ✅ 正式上线
```

---

## 🎯 功能优先级

### P0 - 必须有（MVP）
- [x] 微信登录
- [x] 题库/章节管理（后台）
- [x] 题目录入（后台）
- [ ] 题库/章节列表（小程序）
- [x] 刷题功能（小程序）
- [ ] 答题记录
- [ ] 错题本
- [ ] 用户统计

### P1 - 应该有
- [ ] 收藏功能
- [ ] 打卡功能
- [ ] 笔记功能
- [ ] 数据可视化
- [ ] 用户管理（后台）

### P2 - 可以后续加
- [ ] 考试模式（限时、随机）
- [ ] 排行榜
- [ ] 社区讨论
- [ ] 分享邀请
- [ ] 组卷功能

---

## 📊 进度追踪

### 本周任务 (Week X)

**当前周**: Week 0（准备阶段）

**本周目标**: 确定开发计划，准备开发环境

**任务清单**:
- [x] 分析现有代码
- [x] 制定开发计划
- [x] 创建进度管理文档
- [ ] 确认技术方案
- [ ] 准备开发环境

**本周完成**: 3/5

**遇到的问题**:
- 暂无

**下周计划**:
- 开始 Week 1 任务：核心闭环开发

---

## 📝 每日工作记录

### 2024-11-17 (周日)

**今日任务**:
- [x] 分析后端代码结构
- [x] 分析前端代码结构
- [x] 分析小程序代码结构
- [x] 制定 6 周开发计划
- [x] 创建进度管理文档

**今日产出**:
- 完成项目进度分析
- 完成开发计划文档

**明日计划**:
- 确认开发计划
- 讨论技术细节
- 准备开发环境

---

## ⚠️ 风险管理

### 风险列表

| 风险 | 影响 | 可能性 | 应对策略 |
|------|------|--------|----------|
| 题目录入进度慢 | 高 | 中 | 每天固定录入 20-30 题，考虑批量导入 |
| 开发时间不够 | 高 | 中 | 严格遵守 MVP，砍掉 P2 功能 |
| 技术难点卡住 | 中 | 中 | 单个问题不超过 2 小时，及时求助 |
| 小程序审核被拒 | 中 | 低 | 提前准备协议，避免敏感功能 |
| 用户体验不佳 | 中 | 中 | Week 4 开始内测，快速迭代 |

---

## 📚 参考资料

### 技术文档
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [Vue3 官方文档](https://cn.vuejs.org/)
- [uni-app 官方文档](https://uniapp.dcloud.net.cn/)
- [微信小程序官方文档](https://developers.weixin.qq.com/miniprogram/dev/framework/)

### 项目文档
- [统一认证指南](./unified_auth_guide.md)
- [题目字段映射](./question-field-mapping.md)

---

## 📞 联系方式

**开发者**: Claude Code
**更新频率**: 每日更新
**最后更新**: 2024-11-17

---

## 🎉 里程碑记录

- [ ] **Milestone 1**: 核心闭环完成（Week 1 结束）
- [ ] **Milestone 2**: 错题本和收藏完成（Week 2 结束）
- [ ] **Milestone 3**: 统计功能完成（Week 3 结束）
- [ ] **Milestone 4**: 内测版本发布（Week 4 结束）
- [ ] **Milestone 5**: 正式版本上线（Week 6 结束）

---

**备注**: 本文档是活文档，会根据实际开发进度持续更新。请每天更新"进度追踪"和"每日工作记录"部分。
