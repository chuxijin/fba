<script lang="ts" setup>
import { computed, ref, watch } from 'vue'
import {
  MINI_RENDER_BOOK_EXPORT_PRESETS,
  resolveMiniRenderBookPreset,
} from '@/utils/renderBook'
import type {
  RenderBookExportPresetKey,
  RenderBookExportSubmitPayload,
  RenderBookTemplateKey,
} from '@/utils/renderBook'

const props = withDefaults(defineProps<{
  modelValue: boolean
  templateKey: RenderBookTemplateKey
  title?: string
  totalQuestionCount?: number | null
  confirmText?: string
}>(), {
  title: '导出题本',
  totalQuestionCount: null,
  confirmText: '提交任务',
})

const emit = defineEmits<{
  'update:modelValue': [boolean]
  confirm: [RenderBookExportSubmitPayload]
}>()

const selectedPresetKey = ref<RenderBookExportPresetKey>('questions_only')
const questionCountInput = ref('')
type YearRangePreset = 'unlimited' | 'last_3_years' | 'last_5_years'
const yearRangePreset = ref<YearRangePreset>('unlimited')
const needsRangeFilters = computed(() => props.templateKey === 'practice')
const yearRangeOptions: Array<{ label: string, value: YearRangePreset }> = [
  { label: '不限', value: 'unlimited' },
  { label: '近3年', value: 'last_3_years' },
  { label: '近5年', value: 'last_5_years' },
]
const selectedYearRangeLabel = computed(() => {
  return yearRangeOptions.find(item => item.value === yearRangePreset.value)?.label || '不限'
})

const popupDescription = computed(() => {
  if (props.templateKey === 'practice') {
    return '先选导出样式，再控制题量和年份范围，避免一次导出过多题目。'
  }
  if (props.templateKey === 'wrong_question') {
    return '错题、收藏和笔记统一使用错题本模板导出，这里只需要选择题本样式。'
  }
  return '题库刷题统一使用试卷模板导出，这里只需要选择题本样式。'
})

const recommendedQuestionCount = computed(() => {
  const total = normalizePositiveInteger(props.totalQuestionCount)
  if (!total) {
    return 50
  }
  return Math.min(total, 50)
})

function normalizePositiveInteger(value?: number | null) {
  if (!Number.isFinite(value)) {
    return null
  }

  const normalized = Math.trunc(Number(value))
  if (normalized <= 0) {
    return null
  }

  return normalized
}

function parsePositiveInteger(rawValue: string) {
  const normalized = rawValue.trim()
  if (!normalized) {
    return null
  }
  if (!/^\d+$/.test(normalized)) {
    return null
  }

  return normalizePositiveInteger(Number(normalized))
}

function resetForm() {
  selectedPresetKey.value = 'questions_only'
  questionCountInput.value = needsRangeFilters.value
    ? String(recommendedQuestionCount.value)
    : ''
  yearRangePreset.value = 'unlimited'
}

function closePopup() {
  emit('update:modelValue', false)
}

function chooseYearRange() {
  uni.showActionSheet({
    itemList: yearRangeOptions.map(item => item.label),
    success: (res) => {
      const picked = yearRangeOptions[Number(res.tapIndex)]?.value
      if (picked) {
        yearRangePreset.value = picked
      }
    },
  })
}

function handleConfirm() {
  const presetSettings = resolveMiniRenderBookPreset(selectedPresetKey.value)
  let questionCount: number | null = null
  let yearStart: number | null = null
  let yearEnd: number | null = null

  if (needsRangeFilters.value) {
    const rawQuestionCount = questionCountInput.value.trim()
    questionCount = parsePositiveInteger(rawQuestionCount)
    if (rawQuestionCount && !questionCount) {
      uni.showToast({ title: '题量请输入正整数', icon: 'none' })
      return
    }

    if (!questionCount) {
      questionCount = recommendedQuestionCount.value
    }

    const total = normalizePositiveInteger(props.totalQuestionCount)
    if (total && questionCount > total) {
      questionCount = total
    }

    if (yearRangePreset.value !== 'unlimited') {
      const currentYear = new Date().getFullYear()
      const yearSpan = yearRangePreset.value === 'last_3_years' ? 3 : 5
      yearEnd = currentYear
      yearStart = currentYear - (yearSpan - 1)
    }
  }

  emit('confirm', {
    settings: {
      ...presetSettings,
    },
    questionCount,
    yearStart,
    yearEnd,
  })
  closePopup()
}

watch(() => props.modelValue, (visible) => {
  if (visible) {
    resetForm()
  }
})
</script>

<template>
  <wd-popup
    :model-value="modelValue"
    position="bottom"
    custom-class="rounded-t-3xl overflow-hidden bg-[#FAFAFA]"
    :safe-area-inset-bottom="true"
    :z-index="999999"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <view class="relative p-6 transition-all duration-300">
      <view
        class="absolute right-4 top-4 z-20 h-8 w-8 flex items-center justify-center rounded-full bg-slate-100/70 transition-transform active:scale-90"
        @click="closePopup"
      >
        <view class="i-carbon-close text-lg text-slate-400" />
      </view>

      <view class="mb-6 mt-3 pr-10">
        <view class="text-[20px] text-[#0F172A] font-black tracking-wide">
          {{ title }}
        </view>
        <view class="mt-2 text-[13px] text-[#64748B] leading-5">
          {{ popupDescription }}
        </view>
      </view>

      <view class="mb-5">
        <view class="mb-3 text-[12px] text-[#475569] font-bold">
          导出样式
        </view>
        <view class="flex flex-col gap-3">
          <view
            v-for="item in MINI_RENDER_BOOK_EXPORT_PRESETS"
            :key="item.key"
            class="rounded-2xl border px-4 py-3 transition-all"
            :class="selectedPresetKey === item.key
              ? 'border-[#3B82F6] bg-[#EFF6FF] shadow-[0_8px_24px_-18px_rgba(59,130,246,0.8)]'
              : 'border-[#E2E8F0] bg-white'"
            @click="selectedPresetKey = item.key"
          >
            <view class="flex items-start justify-between gap-3">
              <view class="min-w-0 flex-1">
                <view class="text-[14px] text-[#0F172A] font-bold">
                  {{ item.label }}
                </view>
                <view class="mt-1 text-[12px] text-[#64748B] leading-5">
                  {{ item.description }}
                </view>
              </view>
              <view
                class="mt-0.5 h-5 w-5 flex shrink-0 items-center justify-center rounded-full border"
                :class="selectedPresetKey === item.key ? 'border-[#3B82F6] bg-[#3B82F6]' : 'border-[#CBD5E1] bg-white'"
              >
                <view
                  v-if="selectedPresetKey === item.key"
                  class="i-carbon-checkmark text-[12px] text-white"
                />
              </view>
            </view>
          </view>
        </view>
      </view>

      <view
        v-if="needsRangeFilters"
        class="mb-6 rounded-2xl border border-[#E2E8F0] bg-white px-4 py-4"
      >
        <view class="mb-3 flex items-center justify-between">
          <view class="text-[12px] text-[#475569] font-bold">
            题目范围
          </view>
          <view class="text-[11px] text-[#94A3B8]">
            默认建议 {{ recommendedQuestionCount }} 题
          </view>
        </view>

        <view class="flex items-center gap-2">
          <view class="h-11 flex w-[140px] items-center rounded-2xl bg-[#F8FAFC] px-3">
            <view class="i-carbon-document text-[16px] text-[#94A3B8]" />
            <input
              v-model="questionCountInput"
              type="number"
              class="ml-2 min-w-0 flex-1 bg-transparent text-[14px] text-[#0F172A]"
              placeholder="题量"
              placeholder-class="text-[#CBD5E1] text-[13px]"
            >
          </view>

          <view class="min-w-0 flex flex-1 justify-end" @click="chooseYearRange">
            <view class="h-11 flex w-[140px] items-center justify-between rounded-2xl bg-[#F8FAFC] px-3">
              <view class="flex items-center gap-2 min-w-0">
                <view class="i-carbon-calendar text-[16px] text-[#94A3B8]" />
                <text class="min-w-0 truncate text-[13px] text-[#0F172A] font-bold">
                  {{ selectedYearRangeLabel }}
                </text>
              </view>
              <view class="i-carbon-chevron-down text-[14px] text-[#94A3B8]" />
            </view>
          </view>
        </view>

        <view class="mt-2 text-[11px] text-[#94A3B8] leading-5">
          题量不填会按默认建议；年份范围用于控制试卷年份区间。
        </view>
      </view>

      <view class="flex items-center gap-3">
        <button
          class="popup-btn popup-btn-muted m-0 h-11 flex-1 rounded-2xl text-[14px] text-[#475569] font-bold leading-[44px]"
          @click="closePopup"
        >
          取消
        </button>
        <button
          class="popup-btn popup-btn-primary m-0 h-11 flex-[1.35] rounded-2xl text-[15px] text-white font-bold leading-[44px]"
          @click="handleConfirm"
        >
          {{ confirmText }}
        </button>
      </view>

      <view class="h-safe-area-bottom w-full" />
    </view>
  </wd-popup>
</template>

<style scoped>
.popup-btn::after {
  border: none !important;
}

.popup-btn {
  overflow: visible;
}

.popup-btn-muted {
  background: #e2e8f0;
}

.popup-btn-primary {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  box-shadow: 0 10px 24px -14px rgba(37, 99, 235, 0.8);
}
</style>
