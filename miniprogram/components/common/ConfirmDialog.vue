<template>
  <!-- 使用 UView Plus Modal 组件 -->
  <up-modal
    :show="visible"
    :title="title"
    :content="message"
    :confirm-text="confirmText"
    :cancel-text="cancelText"
    :zoom="true"
    :close-on-click-overlay="false"
    @confirm="handleConfirm"
    @cancel="handleCancel"
  ></up-modal>
</template>

<script setup lang="ts">
interface ConfirmDialogProps {
  visible: boolean
  title?: string
  message: string
  confirmText?: string
  cancelText?: string
}

const props = withDefaults(defineProps<ConfirmDialogProps>(), {
  title: '提示',
  confirmText: '确定',
  cancelText: '取消'
})

const emit = defineEmits<{
  (event: 'confirm'): void
  (event: 'cancel'): void
}>()

function handleConfirm() {
  emit('confirm')
}

function handleCancel() {
  emit('cancel')
}
</script>
