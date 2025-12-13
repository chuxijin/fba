<template>
  <view class="answer-sheet-grid">
    <view class="answer-sheet-grid__header">
      <text class="answer-sheet-grid__title">答题卡</text>
      <view class="answer-sheet-grid__legend">
        <view
          v-for="legend in legends"
          :key="legend.status"
          class="answer-sheet-grid__legend-item"
        >
          <view class="answer-sheet-grid__legend-dot" :class="`answer-sheet-grid__legend-dot--${legend.status}`"></view>
          <text class="answer-sheet-grid__legend-text">{{ legend.label }}</text>
        </view>
      </view>
    </view>

    <view class="answer-sheet-grid__grid">
      <view
        v-for="item in items"
        :key="item.index"
        class="answer-sheet-grid__item"
        :class="getItemClass(item)"
        @tap="handleSelectItem(item.index)"
      >
        {{ item.index }}
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface AnswerSheetItem {
  index: number
  status: string
  isCurrent?: boolean
}

interface AnswerSheetGridProps {
  items: AnswerSheetItem[]
  mode?: 'practice' | 'result'
}

const props = withDefaults(defineProps<AnswerSheetGridProps>(), {
  mode: 'practice'
})

const emit = defineEmits<{
  (event: 'selectItem', index: number): void
}>()

const legends = computed(() => {
  if (props.mode === 'result') {
    return [
      { status: 'correct', label: '答对' },
      { status: 'wrong', label: '答错' },
      { status: 'unanswered', label: '未答' }
    ]
  }

  // practice 模式
  return [
    { status: 'selected', label: '已选' },
    { status: 'unselected', label: '未选' }
  ]
})

function getItemClass(item: AnswerSheetItem): string {
  const classes = []

  // 添加状态类
  if (item.status) {
    classes.push(`answer-sheet-grid__item--${item.status}`)
  }

  // 添加当前题标记（仅在 practice 模式）
  if (props.mode === 'practice' && item.isCurrent) {
    classes.push('answer-sheet-grid__item--current')
  }

  return classes.join(' ')
}

function handleSelectItem(index: number) {
  emit('selectItem', index)
}
</script>

<style scoped lang="scss">
.answer-sheet-grid {
  background: var(--color-bg-card);
  border-radius: 24rpx;
  padding: 40rpx 32rpx;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.05);
}

/* ============ 头部 ============ */
.answer-sheet-grid__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 32rpx;
  flex-wrap: wrap;
  gap: 16rpx;
}

.answer-sheet-grid__title {
  font-size: 32rpx;
  font-weight: 700;
  color: var(--color-text-primary);
}

.answer-sheet-grid__legend {
  display: flex;
  align-items: center;
  gap: 20rpx;
  flex-wrap: wrap;
}

.answer-sheet-grid__legend-item {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.answer-sheet-grid__legend-dot {
  width: 20rpx;
  height: 20rpx;
  border-radius: 50%;
}

.answer-sheet-grid__legend-dot--selected {
  background: #3b82f6;
}

.answer-sheet-grid__legend-dot--unselected {
  background: #94a3b8;
}

.answer-sheet-grid__legend-dot--correct {
  background: #10b981;
}

.answer-sheet-grid__legend-dot--wrong {
  background: #ef4444;
}

.answer-sheet-grid__legend-dot--unanswered {
  background: #94a3b8;
}

.answer-sheet-grid__legend-text {
  font-size: 22rpx;
  color: var(--color-text-secondary);
}

/* ============ 网格 ============ */
.answer-sheet-grid__grid {
  display: flex;
  flex-wrap: wrap;
  gap: 20rpx;
  justify-content: flex-start;
}

/* 使用伪元素填充最后一行，保持整齐对齐 */
.answer-sheet-grid__grid::after {
  content: '';
  width: 80rpx;
  flex-shrink: 0;
}

.answer-sheet-grid__item {
  width: 80rpx;
  height: 80rpx;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16rpx;
  font-size: 28rpx;
  font-weight: 700;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  border: 2rpx solid transparent;
}

/* ============ Practice 模式状态 ============ */
.answer-sheet-grid__item--selected {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(37, 99, 235, 0.08) 100%);
  border-color: #3b82f6;
  color: #2563eb;
}

.answer-sheet-grid__item--unselected {
  background: transparent;
  border-color: rgba(148, 163, 184, 0.3);
  color: var(--color-text-secondary);
}

.answer-sheet-grid__item--current {
  box-shadow: 0 6rpx 20rpx rgba(37, 99, 235, 0.25);
  transform: scale(1.08);
  border-width: 3rpx;
}

/* ============ Result 模式状态 ============ */
.answer-sheet-grid__item--correct {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(5, 150, 105, 0.1) 100%);
  color: #059669;
  border-color: #10b981;
}

.answer-sheet-grid__item--wrong {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(220, 38, 38, 0.1) 100%);
  color: #dc2626;
  border-color: #ef4444;
}

.answer-sheet-grid__item--unanswered {
  background: transparent;
  color: var(--color-text-secondary);
  border-color: rgba(148, 163, 184, 0.4);
  border-style: solid;
}

.answer-sheet-grid__item:active {
  transform: scale(0.95);
}

/* ============ 深色模式 ============ */
@media (prefers-color-scheme: dark) {
  .answer-sheet-grid {
    background: rgba(30, 41, 59, 0.95);
  }

  .answer-sheet-grid__item--selected {
    background: rgba(37, 99, 235, 0.28);
    border-color: rgba(59, 130, 246, 0.75);
    color: rgba(191, 219, 254, 0.92);
  }

  .answer-sheet-grid__item--unselected {
    background: rgba(30, 41, 59, 0.6);
    border-color: rgba(71, 85, 105, 0.55);
    color: rgba(148, 163, 184, 0.9);
  }

  .answer-sheet-grid__item--correct {
    background: rgba(16, 185, 129, 0.28);
    border-color: rgba(45, 212, 191, 0.75);
    color: rgba(209, 250, 229, 0.92);
  }

  .answer-sheet-grid__item--wrong {
    background: rgba(248, 113, 113, 0.28);
    border-color: rgba(248, 113, 113, 0.75);
    color: rgba(254, 202, 202, 0.95);
  }

  .answer-sheet-grid__item--unanswered {
    background: transparent;
    border-color: rgba(71, 85, 105, 0.55);
    color: rgba(148, 163, 184, 0.9);
  }
}
</style>
