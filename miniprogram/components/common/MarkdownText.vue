<template>
  <view class="markdown-text">
    <text
      v-for="(segment, index) in segments"
      :key="index"
      :style="segment.style"
    >{{ segment.text }}</text>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface TextSegment {
  text: string
  style: string
}

interface MarkdownTextProps {
  content: string
}

const props = withDefaults(defineProps<MarkdownTextProps>(), {
  content: ''
})

/**
 * 解析 Markdown 文本为 text 组件数组
 */
const segments = computed<TextSegment[]>(() => {
  if (!props.content) return []

  const result: TextSegment[] = []
  let text = props.content

  // 处理换行符
  text = text.replace(/↵/g, '\n')

  // 正则匹配：加粗、斜体、普通文本
  const regex = /(\*\*(.+?)\*\*)|(\*(.+?)\*)|([^*]+)/g
  let match

  while ((match = regex.exec(text)) !== null) {
    if (match[1]) {
      // **加粗**
      result.push({
        text: match[2],
        style: 'font-weight: bold;'
      })
    } else if (match[3]) {
      // *斜体*
      result.push({
        text: match[4],
        style: 'font-style: italic;'
      })
    } else if (match[5]) {
      // 普通文本
      result.push({
        text: match[5],
        style: ''
      })
    }
  }

  return result
})
</script>

<style scoped>
.markdown-text {
  display: inline;
}
</style>
