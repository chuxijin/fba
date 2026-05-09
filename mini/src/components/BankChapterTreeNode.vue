<script lang="ts" setup>
import { computed } from 'vue'

defineOptions({
  name: 'BankChapterTreeNode',
})

interface ChapterNode {
  id: number
  name: string
  code: string | null
  level: number
  sort_order: number
  parent_id: number | null
  q_count_cache: number
  children: ChapterNode[]
}

interface ChapterProgressNode {
  chapter_id: number
  name: string
  question_count: number
  answer_count: number
  correct_count: number
  correct_ratio: number
  children: ChapterProgressNode[]
}

const props = withDefaults(defineProps<{
  chapter: ChapterNode
  depth?: number
  expandedChapters: Set<number>
  progressMap: Record<number, ChapterProgressNode>
  exportingChapterId: number | null
}>(), {
  depth: 0,
})

const emit = defineEmits<{
  toggle: [id: number]
  start: [chapter: ChapterNode]
  export: [chapter: ChapterNode]
}>()

const hasChildren = computed(() => Boolean(props.chapter.children?.length))
const isExpanded = computed(() => props.expandedChapters.has(props.chapter.id))
const chapterProgress = computed(() => props.progressMap[props.chapter.id])
const displayQuestionCount = computed(() => {
  return chapterProgress.value?.question_count ?? props.chapter.q_count_cache ?? 0
})
const rowPaddingLeft = computed(() => '20px')
const progressPercent = computed(() => {
  const progress = chapterProgress.value
  if (!progress?.question_count)
    return 0

  return Math.round(progress.answer_count / progress.question_count * 100)
})

function handleMainClick() {
  if (hasChildren.value) {
    emit('toggle', props.chapter.id)
    return
  }

  emit('start', props.chapter)
}

function handleExportClick() {
  emit('export', props.chapter)
}
</script>

<template>
  <view>
    <view
      class="border-b border-[#F4F4F4] py-4 active:bg-gray-50"
      :style="{ paddingLeft: rowPaddingLeft, paddingRight: '20px' }"
      @click="handleMainClick"
    >
      <view class="flex items-start justify-between">
        <view class="min-w-0 flex flex-1 items-start">
          <view
            class="mt-[2px] h-[20px] w-[20px] flex shrink-0 items-center justify-center"
            @click.stop="hasChildren ? emit('toggle', chapter.id) : emit('start', chapter)"
          >
            <template v-if="hasChildren">
              <view
                v-if="depth === 0"
                class="h-[16px] w-[16px] flex items-center justify-center rounded-full bg-[#10B981]"
              >
                <view
                  class="i-carbon-chevron-down text-[12px] text-white transition-transform duration-300"
                  style="transition-timing-function: cubic-bezier(0.34, 1.56, 0.64, 1)"
                  :style="{ transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }"
                />
              </view>
              <view
                v-else-if="depth === 1"
                class="h-[16px] w-[16px] flex items-center justify-center rounded-full bg-[#E5E7EB]"
              >
                <view
                  class="i-carbon-chevron-down text-[12px] text-white transition-transform duration-300"
                  style="transition-timing-function: cubic-bezier(0.34, 1.56, 0.64, 1)"
                  :style="{ transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }"
                />
              </view>
              <view
                v-else
                class="i-carbon-chevron-down text-[16px] text-[#A3A3A3] transition-transform duration-300"
                style="transition-timing-function: cubic-bezier(0.34, 1.56, 0.64, 1)"
                :style="{ transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }"
              />
            </template>
            <view v-else class="h-1.5 w-1.5 rounded-full bg-[#CBD5E1]" />
          </view>

          <view class="ml-3 min-w-0 flex-1">
            <view :class="depth === 0 ? 'text-[15px] text-[#222] font-bold' : 'text-[14px] text-[#222] font-medium'">
              {{ chapter.name }}
            </view>
            <view class="mt-1 flex items-center gap-2 text-[11px] text-[#94A3B8]">
              <text>{{ displayQuestionCount }} 题</text>
              <template v-if="chapterProgress?.answer_count">
                <text>·</text>
                <text class="text-[#3B82F6]">已做 {{ chapterProgress.answer_count }}</text>
                <text v-if="chapterProgress.correct_ratio > 0" class="text-[#10B981]">
                  {{ chapterProgress.correct_ratio }}%
                </text>
              </template>
            </view>
          </view>
        </view>
        <view class="ml-2 flex shrink-0 items-center gap-2 whitespace-nowrap">
          <view
            class="rounded-full border border-[#DCFCE7] bg-white px-3 py-1 text-[11px] text-[#059669] font-semibold"
            @click.stop="emit('start', chapter)"
          >
            刷题
          </view>
          <view
            class="rounded-full border border-[#DBEAFE] bg-white px-3 py-1 text-[11px] text-[#2563EB] font-semibold"
            :class="exportingChapterId === chapter.id ? 'bg-[#EFF6FF] opacity-70' : 'bg-white'"
            @click.stop="handleExportClick"
          >
            {{ exportingChapterId === chapter.id ? '导出中' : '题本' }}
          </view>
          <view v-if="!hasChildren" class="i-carbon-chevron-right text-lg text-[#D1D5DB]" />
        </view>
      </view>

      <view v-if="progressPercent > 0" class="mt-2 flex items-center gap-3 text-[12px] text-[#A3A3A3] pl-[32px]">
        <view class="h-[5px] w-1/2 shrink-0 overflow-hidden rounded-full bg-[#E2E8F0]">
          <view
            class="h-full rounded-full from-[#3B82F6] to-[#60A5FA] bg-gradient-to-r transition-all duration-500"
            :style="{ width: `${Math.min(progressPercent, 100)}%` }"
          />
        </view>
        <text>{{ chapterProgress?.answer_count || 0 }}/{{ displayQuestionCount }}</text>
      </view>
    </view>

  </view>
</template>
