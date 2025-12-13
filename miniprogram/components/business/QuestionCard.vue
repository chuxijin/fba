<template>
  <view class="question-card">
    <!-- 加载骨架屏 -->
    <QuestionSkeleton v-if="loading || !question" />

    <!-- 实际题目内容 -->
    <template v-else>
      <!-- 头部 -->
      <view class="question-card__header">
        <text class="question-card__type">{{ question.typeLabel }}</text>
        <CollectIcon :is-active="isCollected" @click="emit('toggleCollect')" />
      </view>

      <!-- 题干 -->
      <up-markdown class="question-card__stem" :content="question.stem || ''"></up-markdown>

      <!-- 选择题（单选/多选/判断） -->
      <view v-if="isChoiceType" class="choice-question">
        <view class="option-list">
          <view
            v-for="option in displayOptions"
            :key="option.value"
            class="option-item"
            :class="getOptionClass(option.value)"
            @tap="() => handleOptionClick(option.value)"
          >
            <view
              class="option-item__indicator"
              :class="{ 'option-item__indicator--square': question.type === 'multiple' }"
            >
              <text class="option-item__letter">{{ option.value }}</text>
            </view>
            <up-markdown class="option-item__content" :content="option.text || ''"></up-markdown>
          </view>
        </view>
      </view>

      <!-- 填空题 -->
      <view v-else-if="question.type === 'fill'" class="fill-question">
        <view v-for="(text, index) in fillValues" :key="index" class="fill-question__item">
          <textarea
            class="fill-question__textarea"
            :placeholder="question.placeholder || `请填写答案 ${index + 1}`"
            :value="text"
            :disabled="disabled || mode === 'memorize' || analysisVisible"
            @input="(e) => handleFillInput(index, e)"
          />
        </view>
      </view>

      <!-- 确定按钮 -->
      <view
        v-if="shouldShowConfirm"
        class="question-card__confirm"
      >
        <view
          class="question-card__confirm-btn"
          :class="{ 'question-card__confirm-btn--disabled': !value }"
          @tap="emit('confirm')"
        >
          确定
        </view>
      </view>

      <!-- 解析 -->
      <view
        v-if="showAnalysisContent && question.analysis"
        class="question-analysis"
      >
        <view class="question-analysis__title">📖 解析</view>
        <up-markdown class="question-analysis__content" :content="question.analysis || ''"></up-markdown>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { BaseQuestion, PracticeMode } from './question-map'
import CollectIcon from '../common/CollectIcon.vue'
import QuestionSkeleton from './QuestionSkeleton.vue'

interface QuestionCardProps {
  question?: BaseQuestion
  mode: PracticeMode
  value?: string
  analysisVisible?: boolean
  disabled?: boolean
  loading?: boolean
  isCollected?: boolean
  shouldShowConfirm?: boolean
}

const props = withDefaults(defineProps<QuestionCardProps>(), {
  value: '',
  analysisVisible: false,
  disabled: false,
  loading: false,
  isCollected: false,
  shouldShowConfirm: false
})

const emit = defineEmits<{
  (event: 'select', value: string): void
  (event: 'confirm'): void
  (event: 'toggleCollect'): void
}>()

// ============ 题型判断 ============
const isChoiceType = computed(() => {
  if (!props.question) return false
  return ['single', 'multiple', 'judgement'].includes(props.question.type)
})

// ============ 选项显示 ============
const displayOptions = computed(() => {
  if (!props.question) return []

  if (props.question.type === 'judgement') {
    return [
      { value: 'A', text: '正确' },
      { value: 'B', text: '错误' }
    ]
  }

  return (props.question.options || []).map(opt => ({
    value: opt.value,
    text: opt.text || ''
  }))
})

// ============ 填空题相关 ============
const fillValues = computed<string[]>(() => {
  if (!props.question || props.question.type !== 'fill') return []

  // 解析 value
  let valueArray: string[]
  try {
    const parsed = JSON.parse(props.value || '[]')
    valueArray = Array.isArray(parsed) ? parsed : [props.value]
  } catch {
    valueArray = props.value ? [props.value] : []
  }

  // 根据答案数量确定填空数
  const answers = props.question.answers || props.question.answer
  const blankCount = (Array.isArray(answers) ? answers.length : 1) || 1

  // 填充到指定数量
  while (valueArray.length < blankCount) {
    valueArray.push('')
  }

  return valueArray
})

// ============ 正确答案集合 ============
const correctSet = computed<Set<string>>(() => {
  if (!props.question) return new Set<string>()

  const answers = props.question.answer
  if (!answers) return new Set<string>()
  if (Array.isArray(answers)) return new Set(answers)
  return new Set([answers])
})

// ============ 解析显示 ============
const showAnalysisContent = computed(() => {
  return props.mode === 'memorize' || (props.mode === 'exercise' && props.analysisVisible)
})

// ============ 选项样式 ============
function getOptionClass(optionValue: string) {
  const classes: Record<string, boolean> = {}

  if (!props.question) return classes

  // 多选题需要解析逗号分隔的值
  let selectedSet: Set<string>
  if (props.question.type === 'multiple') {
    const valueArray = props.value ? props.value.split(',').filter(v => v) : []
    selectedSet = new Set(valueArray)
  } else {
    selectedSet = new Set(props.value ? [props.value] : [])
  }

  const isSelected = selectedSet.has(optionValue)
  const isCorrect = correctSet.value.has(optionValue)

  if (props.analysisVisible) {
    classes['option-item--correct'] = isCorrect
    classes['option-item--wrong'] = isSelected && !isCorrect
  } else if (isSelected) {
    classes['option-item--active'] = true
  }

  return classes
}

// ============ 选项点击 ============
function handleOptionClick(optionValue: string) {
  if (props.disabled || props.analysisVisible || props.mode === 'memorize' || !props.question) {
    return
  }

  let nextValue: string

  if (props.question.type === 'multiple') {
    // 多选题：切换选中状态
    const valueArray = props.value ? props.value.split(',').filter(v => v) : []
    const current = new Set(valueArray)

    if (current.has(optionValue)) {
      current.delete(optionValue)
    } else {
      current.add(optionValue)
    }

    nextValue = Array.from(current).join(',')
  } else {
    // 单选题/判断题：选中或取消选中
    nextValue = props.value === optionValue ? '' : optionValue
  }

  emit('select', nextValue)
}

// ============ 填空题输入 ============
function handleFillInput(index: number, event: any) {
  const inputValue = event?.detail?.value || event?.target?.value || ''
  const current = [...fillValues.value]
  current[index] = inputValue

  // 检查是否至少有一个填空有内容
  const hasContent = current.some(v => v.trim() !== '')

  emit('select', hasContent ? JSON.stringify(current) : '')
}
</script>

<style scoped lang="scss">
.question-card {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  padding: 0;
  box-sizing: border-box;
}

/* ============ 题目头部 ============ */
.question-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
}

.question-card__type {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 10rpx 24rpx;
  border-radius: 20rpx;
  background: rgba(59, 130, 246, 0.16);
  color: #2563eb;
  font-size: 24rpx;
  font-weight: 600;
}

.question-card__stem {
  font-size: 30rpx;
  color: var(--color-text-primary);
  line-height: 1.6;
}

/* 控制 up-markdown 内部间距 */
.question-card__stem :deep(p) {
  margin: 0;
  padding: 0;
}

.question-card__stem :deep(p + p) {
  margin-top: 8rpx;
}

/* ============ 选择题样式 ============ */
.choice-question {
  width: 100%;
}

/* 注意：选项样式已统一定义在 App.vue 全局样式中 */

/* ============ 填空题样式 ============ */
.fill-question {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  box-sizing: border-box;
}

.fill-question__item {
  width: 100%;
  box-sizing: border-box;
}

.fill-question__textarea {
  width: 100%;
  min-height: 160rpx;
  padding: 20rpx 24rpx;
  border-radius: 20rpx;
  border: 2rpx solid var(--color-border);
  background: var(--color-bg-elevated);
  color: var(--color-text-primary);
  font-size: 26rpx;
  line-height: 1.6;
  box-sizing: border-box;
}

.fill-question__textarea:disabled {
  opacity: 0.7;
}

/* ============ 确定按钮 ============ */
.question-card__confirm {
  margin-top: 16rpx;
  padding: 0;
}

.question-card__confirm-btn {
  width: 100%;
  height: 88rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  border-radius: 44rpx;
  font-size: 32rpx;
  font-weight: 700;
  color: #ffffff;
  box-shadow: 0 8rpx 24rpx rgba(59, 130, 246, 0.35);
  transition: transform 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease;
}

.question-card__confirm-btn:active {
  transform: scale(0.97);
  box-shadow: 0 4rpx 12rpx rgba(59, 130, 246, 0.3);
}

.question-card__confirm-btn--disabled {
  background: linear-gradient(135deg, rgba(148, 163, 184, 0.5) 0%, rgba(148, 163, 184, 0.4) 100%);
  box-shadow: none;
  opacity: 0.6;
  pointer-events: none;
}

/* ============ 解析 ============ */
.question-analysis {
  margin-top: 24rpx;
  padding: 24rpx;
  background: rgba(59, 130, 246, 0.05);
  border-left: 4rpx solid #3b82f6;
  border-radius: 12rpx;
}

.question-analysis__title {
  font-size: 26rpx;
  font-weight: 600;
  color: #3b82f6;
  margin-bottom: 12rpx;
}

.question-analysis__content {
  font-size: 26rpx;
  color: var(--color-text-secondary);
  line-height: 1.6;
}
</style>
