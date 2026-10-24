<template>
  <div id="gk-floating-widget-wrapper">
    <!-- 展开态：精致微型卡片 -->
    <div v-if="!isCollapsed" class="gk-float-card">
      <button class="gk-float-close" title="收起悬浮窗" @click="isCollapsed = true">&times;</button>

      <!-- 试卷感知状态小标签 -->
      <div v-if="isReady" class="gk-float-status" :title="paperTitle">
        <span class="gk-status-dot"></span>
        <span class="gk-status-text">{{ questionCount > 0 ? `${questionCount} 题就绪` : '试卷已就绪' }}</span>
      </div>

      <div class="gk-float-btn-group">
        <!-- 主按钮 1: 开始排版 -->
        <button class="gk-float-btn-main" @click="$emit('startReformat')">
          开始排版
        </button>

        <!-- 副按钮 2: 快速打印 -->
        <button class="gk-float-btn-main" @click="$emit('quickPrint')">
          快速打印
        </button>

        <!-- 副按钮 3: 导入错题库（仅在检测到错题时出现） -->
        <button
          v-if="wrongCount > 0"
          class="gk-float-btn-import"
          :class="importButtonClass"
          :disabled="importing"
          :title="importTitle"
          @click="handleImportClick"
        >
          {{ importButtonText }}
        </button>

        <!-- 导入结果 / 失败原因轻提示 -->
        <div v-if="importHint" class="gk-float-import-hint" :class="`is-${importState.status}`">
          <span>{{ importHint }}</span>
          <button v-if="canUndo" class="gk-float-undo-link" @click="$emit('undoImport')">
            撤销本次导入
          </button>
        </div>

        <!-- 辅助按钮: 建议反馈 -->
        <button v-if="reportAvailable" class="gk-float-btn-import" @click="$emit('importReport')">
          导入练习记录
        </button>

        <button class="gk-float-btn-ghost" @click="$emit('feedback')">
          💬 建议反馈
        </button>
      </div>

      <!-- 底部品牌与版本 -->
      <div class="gk-float-footer">
        <div class="gk-brand-row">
          <img v-if="logoUrl" :src="logoUrl" class="gk-brand-logo" alt="Logo" />
          <span class="gk-brand-name">有岸 · 公考排版</span>
        </div>
        <div class="gk-brand-ver">V 1.0.0</div>
      </div>
    </div>

    <!-- 收起态：贴边小图标 -->
    <div
      v-else
      class="gk-float-collapsed-badge"
      title="点击展开公考内容排版"
      @click="isCollapsed = false"
    >
      <img v-if="logoUrl" :src="logoUrl" class="gk-badge-logo" alt="Logo" />
      <span v-else class="gk-badge-icon">📑</span>
      <span v-if="isReady" class="gk-badge-dot"></span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { IDLE_IMPORT_STATE, ImportState } from '../../adapters'

const props = withDefaults(
  defineProps<{
    paperTitle: string
    questionCount: number
    wrongCount?: number
    reportAvailable?: boolean
    importState?: ImportState
  }>(),
  {
    wrongCount: 0,
    reportAvailable: false,
    importState: () => ({ ...IDLE_IMPORT_STATE }),
  }
)

const emit = defineEmits<{
  (e: 'startReformat'): void
  (e: 'quickPrint'): void
  (e: 'feedback'): void
  (e: 'importWrong'): void
  (e: 'undoImport'): void
  (e: 'importReport'): void
}>()

const isCollapsed = ref(false)
const isReady = computed(() => props.questionCount > 0 || Boolean(props.paperTitle))
const logoUrl =
  typeof chrome !== 'undefined' && chrome.runtime?.getURL ? chrome.runtime.getURL('icons/icon48.png') : ''

const importing = computed(() => props.importState.status === 'running')

const importButtonText = computed(() => {
  const state = props.importState
  if (state.status === 'running') {
    return state.done > 0 ? `⏳ 正在导入 ${state.done}/${state.total}…` : `⏳ 正在导入 ${state.total} 道…`
  }
  if (state.status === 'done') {
    return `✅ 已导入 ${state.imported} 道错题`
  }
  if (state.status === 'error') {
    return '⚠️ 导入失败，点击重试'
  }
  return `📥 导入错题库（${props.wrongCount} 题）`
})

const importButtonClass = computed(() => `is-${props.importState.status}`)

/** 仅当上一批导入成功且拿到批次 ID 时，才提供整批撤销 */
const canUndo = computed(
  () => props.importState.status === 'done' && Boolean(props.importState.batchId)
)

const importTitle = computed(() => {
  const state = props.importState
  if (state.status === 'running') return '正在逐题导入到「错题待复盘」，请稍候'
  if (state.status === 'done') return '可在微信小程序「我的题本 → 待复盘错题」中查看'
  if (state.status === 'error') return state.message || '导入失败，请重试'
  return `把当前页面的 ${props.wrongCount} 道错题导入到「错题待复盘」`
})

const importHint = computed(() => {
  const state = props.importState
  if (state.status === 'error') return state.message || '导入失败，请稍后重试'
  if (state.status !== 'done') return ''
  const extras: string[] = []
  if (state.skipped > 0) extras.push(`跳过 ${state.skipped} 道（缺答案或题干）`)
  if (state.failed > 0) extras.push(`失败 ${state.failed} 道`)
  return extras.length > 0 ? extras.join('，') : '可到小程序「待复盘错题」查看'
})

function handleImportClick() {
  if (importing.value) return
  emit('importWrong')
}
</script>
