<template>
  <div class="gk-reformatter-app-root">
    <!-- 1. 悬浮微型卡片 -->
    <FloatingWidget
      :paper-title="paperInfo.title"
      :question-count="paperInfo.questionCount"
      @start-reformat="handleStartReformat"
      @quick-print="handleQuickPrint"
      @feedback="handleFeedback"
    />

    <!-- 2. 设置与交付弹窗 -->
    <SettingsModal
      ref="modalRef"
      v-model="isModalVisible"
      :paper="currentPaper"
      :mistake-meta="mistakeMeta"
      @export="onModalExport"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import FloatingWidget from './FloatingWidget.vue'
import SettingsModal from './SettingsModal.vue'
import { UnifiedPaper, RenderTypographySettings, MistakePageMeta, parseMistakePageMeta } from '../../adapters'

const emit = defineEmits<{
  (e: 'requestReformat'): void
  (e: 'requestQuickPrint'): void
  (e: 'doExport', settings: RenderTypographySettings, target: 'computer_download' | 'mobile_sync'): void
}>()

const isModalVisible = ref(false)
const currentPaper = ref<UnifiedPaper | null>(null)
const mistakeMeta = ref<MistakePageMeta | null>(null)
const modalRef = ref<InstanceType<typeof SettingsModal> | null>(null)

const paperInfo = reactive({
  title: '',
  questionCount: 0,
})

function setPaper(paper: UnifiedPaper) {
  currentPaper.value = paper
  paperInfo.title = paper.title
  paperInfo.questionCount = paper.total_questions

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

function showDelivery(options: { qrCodeUrl?: string; remainingQuota?: number }) {
  modalRef.value?.showDelivery(options)
}

function showError(msg: string) {
  modalRef.value?.showError(msg)
}

function handleStartReformat() {
  emit('requestReformat')
}

function handleQuickPrint() {
  emit('requestQuickPrint')
}

function handleFeedback() {
  alert('如遇到排版或试卷识别问题，请在微信小程序【我的题本】中点击“意见反馈”，我们将第一时间为您解决！')
}

function onModalExport(settings: RenderTypographySettings, target: 'computer_download' | 'mobile_sync') {
  emit('doExport', settings, target)
}

defineExpose({
  setPaper,
  setPaperInfo,
  openModal,
  closeModal,
  showLoading,
  showDelivery,
  showError,
})
</script>
