<script lang="ts" setup>
import type { RenderJobCreatePayload } from '@fba/api-sdk'
import { computed, ref } from 'vue'
import { fbaApi } from '@/api/sdk'
import { useTokenStore } from '@/store'
import {
  BASIC_CALCULATION_TYPES,
  BASIC_CALCULATION_CUSTOM_CONFIG_KEY,
  DEFAULT_BASIC_CALCULATION_CUSTOM_CONFIG,
  createBasicCalculationQuestions,
  encodeBasicCalculationCustomConfig,
  normalizeBasicCalculationCustomConfig,
  type BasicCalculationOrder,
  type BasicCalculationCustomConfig,
  type BasicCalculationMode,
  type BasicCalculationOperator,
  type BasicCalculationSecondMode,
} from '@/utils/basicCalculation'
import { getAppSettings } from '@/utils/appSettings'

defineOptions({
  name: 'BasicCalculation',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'black',
    navigationBarTitleText: '基础计算练习',
  },
})

const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

const keyboardOrder = ref<BasicCalculationOrder>('asc')
const penEnabled = ref(false)
const activeTypeIndex = ref(0)
const questionCount = ref(10)
const exportingQuestions = ref(false)
const tokenStore = useTokenStore()
const showCustomPanel = ref(false)
const exportSelectMode = ref(false)
const selectedExportTypeIndexes = ref<number[]>([])
const customPanelSource = ref<'practice' | 'export'>('practice')
const customConfig = ref<BasicCalculationCustomConfig>(loadCustomConfig())
const customDraftConfig = ref<BasicCalculationCustomConfig>({ ...customConfig.value })

const orderOptions: Array<{ label: string, value: BasicCalculationOrder }> = [
  { label: '正序', value: 'asc' },
  { label: '倒序', value: 'desc' },
  { label: '乱序', value: 'random' },
]
const customModeOptions: Array<{ label: string, value: BasicCalculationMode }> = [
  { label: '标准运算', value: 'standard' },
  { label: '幂运算', value: 'power' },
]
const digitOptions = [1, 2, 3, 4]
const operatorOptions: Array<{ label: string, value: BasicCalculationOperator }> = [
  { label: '+', value: '+' },
  { label: '-', value: '-' },
  { label: '×', value: '×' },
  { label: '÷', value: '÷' },
]
const secondModeOptions: Array<{ label: string, value: BasicCalculationSecondMode }> = [
  { label: '随机位数', value: 'random_digits' },
  { label: '固定数字', value: 'fixed' },
  { label: '随机范围', value: 'range' },
]

const practiceTypes = BASIC_CALCULATION_TYPES

const activePracticeType = computed(() => practiceTypes[activeTypeIndex.value] || practiceTypes[0])
const countLabel = computed(() => `快速(${questionCount.value}题)`)
const customTypeIndex = computed(() => practiceTypes.findIndex(item => item.title === '自定义'))
const isCustomActive = computed(() => activePracticeType.value.title === '自定义')
const selectedExportCount = computed(() => selectedExportTypeIndexes.value.length)
const customConfigSummary = computed(() => {
  const config = customConfig.value
  if (config.mode === 'power') {
    return `${config.firstDigits}位数幂运算`
  }

  const operatorLabel = config.operators.join('')
  if (config.secondMode === 'fixed') {
    return `${config.firstDigits}位数 ${operatorLabel} 固定${config.fixedSecond}`
  }
  if (config.secondMode === 'range') {
    return `${config.firstDigits}位数 ${operatorLabel} ${config.rangeStart}-${config.rangeEnd}`
  }
  return `${config.firstDigits}位数 ${operatorLabel} ${config.secondDigits}位数`
})

function loadCustomConfig() {
  const cached = uni.getStorageSync(BASIC_CALCULATION_CUSTOM_CONFIG_KEY)
  if (!cached) {
    return { ...DEFAULT_BASIC_CALCULATION_CUSTOM_CONFIG }
  }

  return normalizeBasicCalculationCustomConfig(cached)
}

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }
  uni.navigateTo({ url: '/pages/ability-practice/index' })
}

function selectPracticeType(index: number) {
  if (exportSelectMode.value) {
    toggleExportType(index)
    return
  }

  if (practiceTypes[index]?.title === '自定义') {
    customPanelSource.value = 'practice'
    customDraftConfig.value = { ...customConfig.value, operators: [...customConfig.value.operators] }
    showCustomPanel.value = true
    return
  }

  activeTypeIndex.value = index
}

function chooseQuestionCount() {
  const counts = [10, 20, 30, 50]
  uni.showActionSheet({
    itemList: counts.map(item => `快速(${item}题)`),
    success: (res) => {
      const nextCount = counts[Number(res.tapIndex)]
      if (!nextCount) {
        return
      }

      questionCount.value = nextCount
    },
  })
}

function showHelp() {
  uni.showModal({
    title: '触控笔',
    content: '开启后可用于后续手写演算场景，当前先保留开关入口。',
    showCancel: false,
  })
}

function startPractice() {
  const params = [
    `typeIndex=${activeTypeIndex.value}`,
    `count=${questionCount.value}`,
    `order=${keyboardOrder.value}`,
    `pen=${penEnabled.value ? 1 : 0}`,
  ]
  if (isCustomActive.value) {
    params.push('custom=1')
    params.push(`customConfig=${encodeBasicCalculationCustomConfig(customConfig.value)}`)
  }
  uni.navigateTo({ url: `/pages/basic-calculation-session/index?${params.join('&')}` })
}

function isExportTypeSelected(index: number) {
  return selectedExportTypeIndexes.value.includes(index)
}

function toggleExportType(index: number) {
  if (!practiceTypes[index]) {
    return
  }

  if (practiceTypes[index].title === '自定义') {
    customPanelSource.value = 'export'
    customDraftConfig.value = { ...customConfig.value, operators: [...customConfig.value.operators] }
    showCustomPanel.value = true
    return
  }

  if (isExportTypeSelected(index)) {
    selectedExportTypeIndexes.value = selectedExportTypeIndexes.value.filter(item => item !== index)
    return
  }

  selectedExportTypeIndexes.value = [...selectedExportTypeIndexes.value, index].sort((left, right) => left - right)
}

function enterExportSelectMode() {
  if (!tokenStore.updateNowTime().hasLogin) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  if (exportingQuestions.value) {
    return
  }

  exportSelectMode.value = true
  selectedExportTypeIndexes.value = [activeTypeIndex.value]
}

function cancelExportSelectMode() {
  exportSelectMode.value = false
  selectedExportTypeIndexes.value = []
}

function chooseExportMode() {
  return new Promise<'questions_only' | 'questions_with_answers'>((resolve, reject) => {
    uni.showActionSheet({
      itemList: ['仅题目', '题目 + 答案'],
      success: (res) => {
        resolve(Number(res.tapIndex) === 1 ? 'questions_with_answers' : 'questions_only')
      },
      fail: reject,
    })
  })
}

function buildExportPayload(
  contentMode: 'questions_only' | 'questions_with_answers',
  typeIndexes: number[],
): RenderJobCreatePayload {
  const sections = typeIndexes
    .filter(index => practiceTypes[index])
    .map((index) => {
      const type = practiceTypes[index]
      const isCustomType = type.title === '自定义'
      const questions = createBasicCalculationQuestions(index, questionCount.value, isCustomType ? customConfig.value : null)

      return {
        type_index: index,
        type_title: type.title,
        type_hint: isCustomType ? customConfigSummary.value : type.hint,
        custom_config: isCustomType ? customConfig.value : null,
        questions,
      }
    })
  const questions = sections.flatMap(section =>
    section.questions.map(question => ({
      ...question,
      section_title: section.type_title,
      type_index: section.type_index,
      type_title: section.type_title,
    })),
  )
  const includeAnswer = contentMode === 'questions_with_answers'
  const singleSection = sections.length === 1 ? sections[0] : null

  return {
    template_key: 'basic_calculation',
    mode: 'final',
    title: singleSection ? `${singleSection.type_title}题单` : `基础计算组合题单（${sections.length}项）`,
    subtitle: '基础计算练习',
    subject: '基础计算',
    book_kind: 'custom',
    content_mode: contentMode,
    answer_layout: includeAnswer ? 'appendix' : null,
    delivery_mode: 'single_pdf',
    solution_mode: includeAnswer ? 'appendix' : 'none',
    filters: {
      question_count: questions.length,
    },
    options: {
      include_answer: includeAnswer,
      include_analysis: false,
      layout_mode: 'standard',
      theme: 'amber',
      dark_mode: false,
      show_source: false,
    },
    output_targets: {
      question_pdf: true,
      solution_pdf: false,
    },
    metadata: {
      client: 'mini',
      source_type: 'basic_calculation',
      study_domain: getAppSettings().currentDomain,
      type_index: singleSection?.type_index ?? null,
      type_title: singleSection?.type_title ?? '组合训练',
      type_hint: singleSection?.type_hint ?? '',
      keyboard_order: keyboardOrder.value,
      question_count: questions.length,
      per_type_question_count: questionCount.value,
      selected_type_indexes: typeIndexes,
      sections,
      custom_config: sections.some(section => section.custom_config) ? customConfig.value : null,
      questions,
      export_settings: {
        content_mode: contentMode,
        include_answer: includeAnswer,
        layout_mode: 'standard',
        theme: 'amber',
      },
    },
  }
}

function setCustomMode(mode: BasicCalculationMode) {
  customDraftConfig.value = {
    ...customDraftConfig.value,
    mode,
  }
}

function setCustomFirstDigits(digits: number) {
  customDraftConfig.value = {
    ...customDraftConfig.value,
    firstDigits: digits,
  }
}

function toggleCustomOperator(operator: BasicCalculationOperator) {
  const operators = customDraftConfig.value.operators.includes(operator)
    ? customDraftConfig.value.operators.filter(item => item !== operator)
    : [...customDraftConfig.value.operators, operator]

  customDraftConfig.value = {
    ...customDraftConfig.value,
    operators: operators.length ? operators : [operator],
  }
}

function setCustomSecondMode(mode: BasicCalculationSecondMode) {
  customDraftConfig.value = {
    ...customDraftConfig.value,
    secondMode: mode,
  }
}

function setCustomSecondDigits(digits: number) {
  customDraftConfig.value = {
    ...customDraftConfig.value,
    secondDigits: digits,
  }
}

function updateCustomNumber(key: 'fixedSecond' | 'rangeStart' | 'rangeEnd', value: string) {
  customDraftConfig.value = normalizeBasicCalculationCustomConfig({
    ...customDraftConfig.value,
    [key]: Number(value),
  })
}

function closeCustomPanel() {
  showCustomPanel.value = false
}

function confirmCustomPanel() {
  const normalized = normalizeBasicCalculationCustomConfig(customDraftConfig.value)
  customConfig.value = normalized
  uni.setStorageSync(BASIC_CALCULATION_CUSTOM_CONFIG_KEY, normalized)
  if (customTypeIndex.value >= 0) {
    if (customPanelSource.value === 'export') {
      if (!selectedExportTypeIndexes.value.includes(customTypeIndex.value)) {
        selectedExportTypeIndexes.value = [...selectedExportTypeIndexes.value, customTypeIndex.value].sort((left, right) => left - right)
      }
      showCustomPanel.value = false
      return
    }

    activeTypeIndex.value = customTypeIndex.value
  }
  showCustomPanel.value = false
}

function useRecentCustomConfig() {
  customDraftConfig.value = {
    ...customConfig.value,
    operators: [...customConfig.value.operators],
  }
}

async function exportQuestions() {
  if (!tokenStore.updateNowTime().hasLogin) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  if (exportingQuestions.value) {
    return
  }
  if (!selectedExportTypeIndexes.value.length) {
    uni.showToast({ title: '请至少选择一项', icon: 'none' })
    return
  }

  let contentMode: 'questions_only' | 'questions_with_answers'
  try {
    contentMode = await chooseExportMode()
  }
  catch {
    return
  }

  exportingQuestions.value = true
  uni.showLoading({ title: '提交任务中...' })
  try {
    const job = await fbaApi.renderBook.createJob(buildExportPayload(contentMode, selectedExportTypeIndexes.value))
    await fbaApi.renderBook.dispatchJob(job.job_id, true)
    cancelExportSelectMode()
    uni.showModal({
      title: '已提交导出任务',
      content: '基础计算题单正在后台生成，稍后可到「我的 - 我的题本」查看并下载。',
      confirmText: '去查看',
      cancelText: '知道了',
      success: (res) => {
        if (res.confirm) {
          uni.navigateTo({ url: '/pages/my-render-books/index' })
        }
      },
    })
  }
  catch (error: any) {
    console.error('导出基础计算题单失败:', error)
    uni.showToast({ title: error?.message || '导出失败', icon: 'none' })
  }
  finally {
    exportingQuestions.value = false
    uni.hideLoading()
  }
}

function openHistory() {
  uni.showToast({ title: '历史记录正在接入中', icon: 'none' })
}
</script>

<template>
  <view class="min-h-screen bg-[#F5F1EA] text-[#111827]">
    <view class="relative z-10 w-full bg-[#F5F1EA]" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center rounded-full bg-white/90 text-[#475569] shadow-sm active:scale-95" @click="goBack">
          <view class="i-carbon-chevron-left text-xl" />
        </view>
        <text class="text-lg font-bold tracking-widest">
          基础计算练习
        </text>
      </view>
    </view>

    <view class="px-3 pb-[180px] pt-2">
      <view class="mb-3 flex items-center gap-2">
        <text class="shrink-0 text-[13px] text-[#334155] font-bold">键盘</text>
        <view class="flex overflow-hidden rounded-md bg-[#E7E2D8] p-0.5">
          <view
            v-for="option in orderOptions"
            :key="option.value"
            class="rounded px-3 py-2 text-[13px] font-bold transition-all"
            :class="keyboardOrder === option.value ? 'bg-white text-[#1F2937] shadow-sm' : 'text-[#7C7062]'"
            @click="keyboardOrder = option.value"
          >
            {{ option.label }}
          </view>
        </view>

        <view class="ml-auto flex items-center gap-2">
          <text class="text-[13px] text-[#334155] font-bold">触控笔</text>
          <switch :checked="penEnabled" color="#F59E0B" style="transform: scale(0.72)" @change="penEnabled = $event.detail.value" />
          <text class="text-[13px] text-[#334155] font-bold">{{ penEnabled ? '开' : '关' }}</text>
          <view class="h-5 w-5 flex items-center justify-center rounded-full bg-white/90 text-[12px] text-[#94A3B8] font-black" @click="showHelp">
            ?
          </view>
        </view>
      </view>

      <view v-if="exportSelectMode" class="mb-3 rounded-xl border border-[#F2DDA8] bg-[#FFF7E1] px-4 py-3 shadow-[0_8px_24px_-22px_rgba(146,64,14,0.45)]">
        <view class="flex items-center gap-2">
          <view class="i-carbon-checkbox-checked-filled text-lg text-[#D97706]" />
          <text class="text-[14px] text-[#78350F] font-black">选择要导出的练习项目</text>
          <text class="ml-auto text-[12px] text-[#B45309] font-bold">已选 {{ selectedExportCount }} 项</text>
        </view>
        <view class="mt-1 text-[12px] text-[#92400E] leading-relaxed">
          每个项目生成 {{ questionCount }} 题，最后合并成一份题单。
        </view>
      </view>

      <view class="grid grid-cols-3 gap-2">
        <view
          v-for="(item, index) in practiceTypes"
          :key="item.title"
          class="relative h-[54px] flex items-center justify-center rounded-md px-1 text-center text-[15px] font-black leading-tight active:scale-[0.98]"
          :class="exportSelectMode
            ? (isExportTypeSelected(index) ? 'bg-[#1F2937] text-[#FDE68A] shadow-[0_8px_20px_-14px_rgba(31,41,55,0.7)]' : 'bg-white/90 text-[#1F2937] ring-1 ring-[#E7E2D8]')
            : (activeTypeIndex === index ? 'bg-[#1F2937] text-[#FDE68A] shadow-[0_8px_20px_-14px_rgba(31,41,55,0.7)]' : 'bg-[#E8EDF5] text-[#1F2937]')"
          @click="selectPracticeType(index)"
        >
          <view
            v-if="exportSelectMode"
            class="absolute right-1.5 top-1.5 h-4 w-4 flex items-center justify-center rounded-full text-[10px] font-black"
            :class="isExportTypeSelected(index) ? 'bg-[#FDE68A] text-[#1F2937]' : 'bg-[#E7E2D8] text-transparent'"
          >
            ✓
          </view>
          {{ item.title }}
        </view>
      </view>

      <view class="mt-5 flex items-center justify-between rounded-md bg-[#E8EDF5] px-4 py-3 active:scale-[0.99]" @click="chooseQuestionCount">
        <text class="text-[15px] font-black">题量</text>
        <view class="flex items-center text-[13px] text-[#64748B]">
          <text>{{ countLabel }}</text>
          <view class="i-carbon-chevron-right ml-1 text-[16px]" />
        </view>
      </view>

      <view class="mt-4 rounded-md border border-[#E7E2D8] bg-white/80 px-4 py-3 shadow-[0_2px_12px_-10px_rgba(31,41,55,0.22)]">
        <view class="text-[13px] text-[#92400E] font-black">
          {{ activePracticeType.title }}
        </view>
        <view class="mt-1 text-[12px] text-[#64748B] leading-relaxed">
          {{ isCustomActive ? customConfigSummary : activePracticeType.hint }}
        </view>
      </view>
    </view>

    <view class="fixed bottom-0 left-0 right-0 bg-[#F5F1EA]/96 px-3 pb-[calc(env(safe-area-inset-bottom)+12px)] pt-3 shadow-[0_-10px_24px_-22px_rgba(31,41,55,0.55)]">
      <template v-if="exportSelectMode">
        <view class="mb-2 flex items-center justify-between px-1 text-[12px] text-[#7C7062]">
          <text>合计 {{ selectedExportCount * questionCount }} 题</text>
          <text>可继续点选上方项目</text>
        </view>
        <view class="grid grid-cols-[0.8fr_1.2fr] gap-3">
          <view class="h-11 flex items-center justify-center rounded-md bg-white/90 text-[15px] text-[#7C7062] font-black active:scale-[0.99]" @click="cancelExportSelectMode">
            取消
          </view>
          <view class="h-11 flex items-center justify-center rounded-md bg-[#F59E0B] text-[15px] text-[#111827] font-black shadow-[0_8px_18px_-14px_rgba(245,158,11,0.85)] active:scale-[0.99]" @click="exportQuestions">
            {{ exportingQuestions ? '导出中...' : `导出已选 ${selectedExportCount} 项` }}
          </view>
        </view>
      </template>
      <template v-else>
        <view class="h-11 flex items-center justify-center rounded-md bg-[#F59E0B] text-[16px] text-[#111827] font-black shadow-[0_8px_18px_-14px_rgba(245,158,11,0.85)] active:scale-[0.99]" @click="startPractice">
          开始练习
        </view>
        <view class="mt-4 grid grid-cols-2 gap-3">
          <view class="h-11 flex items-center justify-center rounded-md bg-[#E8EDF5] text-[15px] font-black active:scale-[0.99]" @click="enterExportSelectMode">
            导出题目
          </view>
          <view class="h-11 flex items-center justify-center rounded-md bg-[#E8EDF5] text-[15px] font-black active:scale-[0.99]" @click="openHistory">
            历史记录
          </view>
        </view>
      </template>
    </view>

    <view v-if="showCustomPanel" class="fixed inset-0 z-50 flex items-end bg-black/30" @click="closeCustomPanel">
      <view class="max-h-[88vh] w-full overflow-y-auto rounded-t-2xl bg-[#F8F5EF] pb-[calc(env(safe-area-inset-bottom)+12px)] shadow-[0_-18px_40px_-24px_rgba(15,23,42,0.45)]" @click.stop>
        <view class="flex items-center border-b border-[#E7E2D8] px-5 py-3">
          <view class="flex overflow-hidden rounded-lg bg-[#E7E2D8] p-1">
            <view
              v-for="option in customModeOptions"
              :key="option.value"
              class="rounded-md px-5 py-2 text-[14px] font-black"
              :class="customDraftConfig.mode === option.value ? 'bg-white text-[#B45309] shadow-sm' : 'text-[#7C7062]'"
              @click="setCustomMode(option.value)"
            >
              {{ option.label }}
            </view>
          </view>
          <view class="i-carbon-close ml-auto text-xl text-[#8A8177]" @click="closeCustomPanel" />
        </view>

        <view class="px-5 py-4">
          <view class="mb-5">
            <view class="mb-3 text-[14px] text-[#4B5563] font-black">
              第一个数
            </view>
            <view class="grid grid-cols-4 gap-3">
              <view
                v-for="digits in digitOptions"
                :key="`first-${digits}`"
                class="h-10 flex items-center justify-center rounded-md text-[14px] font-black"
                :class="customDraftConfig.firstDigits === digits ? 'bg-[#1F2937] text-[#FDE68A]' : 'bg-white/80 text-[#7C7062]'"
                @click="setCustomFirstDigits(digits)"
              >
                {{ digits }}位数
              </view>
            </view>
          </view>

          <view v-if="customDraftConfig.mode === 'standard'" class="mb-5">
            <view class="mb-3 text-[14px] text-[#4B5563] font-black">
              运算符号（可多选）
            </view>
            <view class="grid grid-cols-4 gap-3">
              <view
                v-for="operator in operatorOptions"
                :key="operator.value"
                class="h-10 flex items-center justify-center rounded-md text-[18px] font-black"
                :class="customDraftConfig.operators.includes(operator.value) ? 'bg-[#1F2937] text-[#FDE68A]' : 'bg-white/80 text-[#7C7062]'"
                @click="toggleCustomOperator(operator.value)"
              >
                {{ operator.label }}
              </view>
            </view>
          </view>

          <view class="mb-5">
            <view class="mb-3 text-[14px] text-[#4B5563] font-black">
              第二个数
            </view>
            <view class="grid grid-cols-3 gap-3">
              <view
                v-for="option in secondModeOptions"
                :key="option.value"
                class="h-10 flex items-center justify-center rounded-md text-[14px] font-black"
                :class="customDraftConfig.secondMode === option.value ? 'bg-[#1F2937] text-[#FDE68A]' : 'bg-white/80 text-[#7C7062]'"
                @click="setCustomSecondMode(option.value)"
              >
                {{ option.label }}
              </view>
            </view>

            <view v-if="customDraftConfig.secondMode === 'random_digits'" class="mt-3 grid grid-cols-4 gap-3">
              <view
                v-for="digits in digitOptions"
                :key="`second-${digits}`"
                class="h-10 flex items-center justify-center rounded-md text-[14px] font-black"
                :class="customDraftConfig.secondDigits === digits ? 'bg-[#1F2937] text-[#FDE68A]' : 'bg-white/80 text-[#7C7062]'"
                @click="setCustomSecondDigits(digits)"
              >
                {{ digits }}位数
              </view>
            </view>

            <view v-if="customDraftConfig.secondMode === 'fixed'" class="mt-3 rounded-md bg-white/80 px-3 py-2">
              <input
                class="h-9 text-[15px] text-[#111827]"
                type="number"
                :value="String(customDraftConfig.fixedSecond)"
                placeholder="输入固定数字"
                @input="updateCustomNumber('fixedSecond', $event.detail.value)"
              >
            </view>

            <view v-if="customDraftConfig.secondMode === 'range'" class="mt-3 grid grid-cols-2 gap-3">
              <view class="rounded-md bg-white/80 px-3 py-2">
                <input
                  class="h-9 text-[15px] text-[#111827]"
                  type="number"
                  :value="String(customDraftConfig.rangeStart)"
                  placeholder="最小值"
                  @input="updateCustomNumber('rangeStart', $event.detail.value)"
                >
              </view>
              <view class="rounded-md bg-white/80 px-3 py-2">
                <input
                  class="h-9 text-[15px] text-[#111827]"
                  type="number"
                  :value="String(customDraftConfig.rangeEnd)"
                  placeholder="最大值"
                  @input="updateCustomNumber('rangeEnd', $event.detail.value)"
                >
              </view>
            </view>
          </view>

          <view class="mb-5">
            <view class="mb-3 text-[14px] text-[#4B5563] font-black">
              最近使用
            </view>
            <view class="inline-flex rounded-md bg-white/80 px-4 py-3 text-[13px] text-[#7C7062] font-bold" @click="useRecentCustomConfig">
              {{ customConfigSummary }}
            </view>
          </view>

          <view class="grid grid-cols-2 gap-3 border-t border-[#E7E2D8] pt-3">
            <view class="h-11 flex items-center justify-center rounded-md bg-white/80 text-[15px] text-[#7C7062] font-black active:scale-[0.99]" @click="closeCustomPanel">
              取消
            </view>
            <view class="h-11 flex items-center justify-center rounded-md bg-[#F59E0B] text-[15px] text-[#111827] font-black active:scale-[0.99]" @click="confirmCustomPanel">
              确定
            </view>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>
