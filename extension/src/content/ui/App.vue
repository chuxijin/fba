<template>
  <div class="gk-reformatter-app-root">
    <!-- 1. 悬浮微型卡片 -->
    <FloatingWidget
      :paper-title="paperInfo.title"
      :question-count="paperInfo.questionCount"
      :wrong-count="wrongCount"
      :import-state="importState"
      :report-available="reportAvailable"
      :feedback-error="feedbackError"
      @start-reformat="handleStartReformat"
      @feedback="handleFeedback"
      @import-wrong="handleImportWrong"
      @undo-import="handleUndoImport"
      @import-report="handleImportReport"
    />

    <!-- 2. 设置与交付弹窗 -->
    <SettingsModal
      ref="modalRef"
      v-model="isModalVisible"
      :paper="currentPaper"
      :mistake-meta="mistakeMeta"
      @export="onModalExport"
    />
    <PracticeReportImport v-if="reportVisible" :draft="reportDraft" :status="reportStatus" :message="reportMessage" @close="reportVisible = false" @retry="handleImportReport" @save="emit('saveReport', $event)" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import FloatingWidget from './FloatingWidget.vue'
import SettingsModal from './SettingsModal.vue'
import PracticeReportImport from './PracticeReportImport.vue'
import { fenbiReportRoute } from '../../adapters/fenbi/report'
import type { PracticeReportPayload } from '../../adapters/fenbi/report'
import type { DeliveryView } from '../../utils/export-delivery'
import { exportMessage } from '../../utils/export-flow'
import {
  UnifiedPaper,
  RenderTypographySettings,
  MistakePageMeta,
  parseMistakePageMeta,
  countWrongQuestions,
  IDLE_IMPORT_STATE,
  ImportState,
} from '../../adapters'

const emit = defineEmits<{
  (e: 'requestReformat'): void
  (e: 'doExport', settings: RenderTypographySettings, target: 'computer_download' | 'mobile_sync'): void
  (e: 'importWrong'): void
  (e: 'undoImport'): void
  (e: 'importReport'): void
  (e: 'saveReport', draft: PracticeReportPayload): void
}>()

const isModalVisible = ref(false)
const feedbackError = ref('')
const currentPaper = ref<UnifiedPaper | null>(null)
const mistakeMeta = ref<MistakePageMeta | null>(null)
const modalRef = ref<InstanceType<typeof SettingsModal> | null>(null)

const paperInfo = reactive({
  title: '',
  questionCount: 0,
})

/** 当前试卷里可导入的错题数量（0 时悬浮窗不显示导入按钮） */
const wrongCount = ref(0)
const importState = ref<ImportState>({ ...IDLE_IMPORT_STATE })
const reportAvailable = ref(Boolean(fenbiReportRoute(location.href)))
const reportVisible = ref(false)
const reportDraft = ref<PracticeReportPayload|null>(null)
const reportStatus = ref('idle')
const reportMessage = ref('')

function handleImportReport() {
  reportVisible.value = true
  reportDraft.value = null
  setReportStatus('loading')
  emit('importReport')
}
function setReportDraft(draft: PracticeReportPayload) {
  reportDraft.value = draft
  setReportStatus('ready')
}
function setReportStatus(status: string, message = '') {
  reportStatus.value = status
  reportMessage.value = message
}

function setPaper(paper: UnifiedPaper) {
  currentPaper.value = paper
  paperInfo.title = paper.title
  paperInfo.questionCount = paper.total_questions
  wrongCount.value = countWrongQuestions(paper)

  // 解析错题元数据
  const parsed = parseMistakePageMeta(location.href, paper.title)
  if (parsed && parsed.total > 0) {
    mistakeMeta.value = parsed
  } else if (paper.metadata?.mistakeMeta) {
    mistakeMeta.value = paper.metadata.mistakeMeta
  } else {
    mistakeMeta.value = null
  }
}

function setPaperInfo(title: string, count: number) {
  paperInfo.title = title
  paperInfo.questionCount = count
}

/** 试卷信息被清空（SPA 路由切换）时同步复位导入能力 */
function resetPaper() {
  reportAvailable.value = Boolean(fenbiReportRoute(location.href))
  reportVisible.value = false
  reportDraft.value = null
  currentPaper.value = null
  paperInfo.title = ''
  paperInfo.questionCount = 0
  wrongCount.value = 0
  mistakeMeta.value = null
  importState.value = { ...IDLE_IMPORT_STATE }
}

function setImportState(state: ImportState) {
  importState.value = { ...state }
}

function openModal() {
  isModalVisible.value = true
}

function closeModal() {
  isModalVisible.value = false
}

function showLoading(target: 'computer_download' | 'mobile_sync') {
  isModalVisible.value = true
  modalRef.value?.showLoading(target)
}

function showDelivery(options: DeliveryView) {
  modalRef.value?.showDelivery(options)
}

function showError(msg: string) {
  modalRef.value?.showError(msg)
}

function handleStartReformat() {
  emit('requestReformat')
}

async function handleFeedback() {
  feedbackError.value = ''
  try { await exportMessage('OPEN_SUPPORT', { section: 'feedback' }) }
  catch (error: any) { feedbackError.value = error?.message || '无法打开反馈页，请从插件弹窗重试' }
}

function handleImportWrong() {
  emit('importWrong')
}

function handleUndoImport() {
  emit('undoImport')
}

function onModalExport(settings: RenderTypographySettings, target: 'computer_download' | 'mobile_sync') {
  emit('doExport', settings, target)
}

defineExpose({
  setReportDraft,
  setReportStatus,
  setPaper,
  setPaperInfo,
  setImportState,
  resetPaper,
  openModal,
  closeModal,
  showLoading,
  showDelivery,
  showError,
})
</script>
