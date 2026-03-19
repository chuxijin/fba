<template>
  <wd-message-box selector="confirm-dialog-box"></wd-message-box>
</template>

<script setup lang="ts">
import { watch } from 'vue'
import { useMessage } from 'wot-design-uni'

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

const messageBox = useMessage('confirm-dialog-box')

watch(
  () => props.visible,
  (val) => {
    if (val) {
      messageBox
        .confirm({
          title: props.title,
          msg: props.message,
          confirmButtonText: props.confirmText,
          cancelButtonText: props.cancelText
        })
        .then(() => {
          emit('confirm')
        })
        .catch(() => {
          emit('cancel')
        })
    }
  }
)
</script>
