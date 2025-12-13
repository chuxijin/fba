# Mock数据说明

## 📁 文件说明

### `questions.ts`
包含所有6种题型的完整示例数据，用于刷题页面测试。

## 📊 题型列表

| 题型 | 英文标识 | 数量 | 说明 |
|------|---------|------|------|
| 单选题 | `single` | 3道 | 含选项A-D，单个正确答案 |
| 多选题 | `multiple` | 2道 | 含选项A-E，多个正确答案 |
| 判断题 | `judgement` | 3道 | 正确/错误选择 |
| 填空题 | `fill` | 3道 | 需要输入文字答案 |
| 材料题 | `material` | 1道 | 含材料+2道子题 |
| 问答题 | `qa` | 2道 | 开放式回答，有参考答案 |

**总计**: 14道题目（包含材料题中的子题）

## 🎯 使用方法

### 1. 在刷题页面使用

```typescript
import { allQuestions, mockBankInfo } from '@/mock/questions'

// 获取所有题目
const questions = allQuestions

// 获取题库信息
const bankInfo = mockBankInfo
```

### 2. 按题型获取

```typescript
import { questionsByType } from '@/mock/questions'

// 只获取单选题
const singleQuestions = questionsByType.single

// 只获取多选题
const multipleQuestions = questionsByType.multiple
```

### 3. 完整示例

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import { allQuestions } from '@/mock/questions'
import { questionComponentMap } from '@/components/practice/question-map'

const currentIndex = ref(0)

// 当前题目
const currentQuestion = computed(() => {
  return allQuestions[currentIndex.value]
})

// 动态组件
const questionComponent = computed(() => {
  return questionComponentMap[currentQuestion.value.type]
})

// 切换题目
function nextQuestion() {
  if (currentIndex.value < allQuestions.length - 1) {
    currentIndex.value++
  }
}
</script>

<template>
  <component
    :is="questionComponent"
    :question="currentQuestion"
    mode="practice"
  />
</template>
```

## 📝 题目数据结构

### 基础题目（单选/多选/判断）

```typescript
{
  id: 'single-001',              // 题目ID
  type: 'single',                // 题型
  typeLabel: '单选题',           // 题型标签
  stem: '题干内容...',           // 题目主干
  options: [                     // 选项（仅选择题）
    { value: 'A', text: '选项A' },
    { value: 'B', text: '选项B' }
  ],
  answer: ['C'],                 // 正确答案
  analysis: '解析内容...'        // 答案解析
}
```

### 填空题

```typescript
{
  id: 'fill-001',
  type: 'fill',
  typeLabel: '填空题',
  stem: '题干内容...',
  answers: ['答案1', '答案2'],   // 可能有多个空
  placeholder: '请输入答案',
  analysis: '解析内容...'
}
```

### 材料题

```typescript
{
  id: 'material-001',
  type: 'material',
  typeLabel: '材料分析题',
  stem: '请根据以下材料回答问题：',
  materials: [                   // 材料内容（可多段）
    '材料一：...',
    '材料二：...'
  ],
  subQuestions: [                // 子题列表
    {
      id: 'material-001-sub-1',
      type: 'single',
      stem: '（1）问题1',
      // ... 其他字段
    }
  ],
  analysis: '综合解析...'
}
```

### 问答题

```typescript
{
  id: 'qa-001',
  type: 'qa',
  typeLabel: '问答题',
  stem: '题目要求...',
  reference: '参考答案内容...',  // 完整参考答案
  analysis: '答题要点...'
}
```

## 🎨 题目内容说明

所有mock题目内容均为**2024年时政热点**相关内容：

- **单选题**: 习近平新时代中国特色社会主义思想、中央一号文件等
- **多选题**: 核心内容、战略安排等
- **判断题**: 重要论断判断
- **填空题**: 根本宗旨、中心任务、本质要求等
- **材料题**: 高质量发展材料分析
- **问答题**: 中国式现代化、重要论断理解等

## 🚀 快速开始

1. **查看效果**
   - 进入刷题页面 `/pages/practice/index`
   - 使用"上一题"/"下一题"按钮切换
   - 查看所有6种题型的展示效果

2. **自定义题目**
   - 复制现有题目结构
   - 修改题干、选项、答案等内容
   - 添加到对应题型数组中

3. **扩展题库**
   - 在 `mock/questions.ts` 中添加更多题目
   - 或创建新的 mock 文件（如 `questions-2.ts`）
   - 导入到页面中使用

## ⚠️ 注意事项

1. **题型标识必须匹配**
   - `type` 字段必须是 6 种题型之一
   - 确保与 `question-map.ts` 中定义的一致

2. **材料题子题处理**
   - 子题需要类型断言：`as ChoiceQuestion`
   - 子题ID建议使用 `父题ID-sub-序号` 格式

3. **答案格式**
   - 单选题：`answer: ['A']`（数组，单个元素）
   - 多选题：`answer: ['A', 'B', 'C']`（数组，多个元素）
   - 判断题：`answer: ['A']`（A=正确，B=错误）
   - 填空题：`answers: ['答案1', '答案2']`
   - 问答题：`reference: '完整答案'`

## 📚 后续计划

- [ ] 添加更多题型（简答题、论述题等）
- [ ] 增加题目难度标识
- [ ] 添加知识点标签
- [ ] 支持题目搜索和筛选
- [ ] 添加错题本功能
- [ ] 支持题目收藏

---

**提示**: 这是测试用的mock数据，正式环境请从后端API获取真实数据。
