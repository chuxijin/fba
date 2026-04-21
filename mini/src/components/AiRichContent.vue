<script lang="ts" setup>
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import { computed } from 'vue'
// @ts-expect-error mp-html uni-app package does not ship TS declarations for this entry.
import mpHtml from 'mp-html/dist/uni-app/components/mp-html/mp-html'
import { replaceHtmlWithCachedMedia } from '@/utils/questionMediaCache'

defineOptions({ name: 'AiRichContent' })

type ContentFormat = 'auto' | 'markdown' | 'html' | 'text'

const props = withDefaults(defineProps<{
  content?: string | null
  format?: ContentFormat
  selectable?: boolean
}>(), {
  content: '',
  format: 'auto',
  selectable: true,
})

const markdownIt = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  typographer: false,
  highlight(code, language) {
    let highlighted = ''
    if (language && hljs.getLanguage(language)) {
      highlighted = hljs.highlight(code, { language, ignoreIllegals: true }).value
    }
    else {
      highlighted = hljs.highlightAuto(code).value
    }

    return `<pre class="ai-code-block"><code class="hljs${language ? ` language-${language}` : ''}">${highlighted}</code></pre>`
  },
})

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function looksLikeHtml(value: string) {
  return /<([a-z][\w-]*)(\s[^>]*)?>/i.test(value)
}

function looksLikeMarkdown(value: string) {
  return /(^|\n)\s{0,3}(#{1,6}\s|[-*+]\s|\d+\.\s|>\s|```|~~~|\|.+\|)/m.test(value)
    || /\[[^\]]+\]\([^)]+\)/.test(value)
    || /`[^`]+`/.test(value)
}

function renderPlainText(value: string) {
  const escaped = escapeHtml(value)
  const paragraphs = escaped
    .split(/\n{2,}/)
    .map(item => item.trim())
    .filter(Boolean)

  if (!paragraphs.length) {
    return ''
  }

  return paragraphs
    .map(item => `<p>${item.replace(/\n/g, '<br/>')}</p>`)
    .join('')
}

const renderedHtml = computed(() => {
  const raw = String(props.content || '').trim()
  if (!raw) {
    return ''
  }

  let nextHtml = ''
  if (props.format === 'html' || (props.format === 'auto' && looksLikeHtml(raw))) {
    nextHtml = raw
  }
  else if (props.format === 'markdown' || (props.format === 'auto' && looksLikeMarkdown(raw))) {
    nextHtml = markdownIt.render(raw)
  }
  else {
    nextHtml = renderPlainText(raw)
  }

  return replaceHtmlWithCachedMedia(nextHtml)
})

const tagStyle = {
  table: 'width:100%;border-collapse:collapse;table-layout:auto;margin:12px 0;border:1px solid #dbe3ef;border-radius:12px;overflow:hidden;background:#ffffff;',
  th: 'padding:10px 12px;border:1px solid #dbe3ef;background:#f8fafc;color:#334155;font-weight:700;font-size:12px;text-align:left;',
  td: 'padding:10px 12px;border:1px solid #e2e8f0;color:#475569;font-size:13px;line-height:1.8;vertical-align:top;',
  blockquote: 'margin:12px 0;padding:10px 14px;border-left:4px solid #86efac;background:#f0fdf4;color:#166534;border-radius:12px;',
  pre: 'margin:12px 0;background:#0f172a;border-radius:14px;overflow:auto;',
  code: 'font-family:SFMono-Regular,Consolas,Monaco,monospace;',
  p: 'margin:10px 0;color:#334155;line-height:1.85;',
  ul: 'margin:10px 0;padding-left:20px;color:#334155;line-height:1.85;',
  ol: 'margin:10px 0;padding-left:20px;color:#334155;line-height:1.85;',
  li: 'margin:6px 0;color:#334155;line-height:1.85;',
  h1: 'margin:16px 0 12px;color:#0f172a;font-size:22px;font-weight:800;line-height:1.4;',
  h2: 'margin:16px 0 12px;color:#0f172a;font-size:19px;font-weight:800;line-height:1.45;',
  h3: 'margin:14px 0 10px;color:#0f172a;font-size:17px;font-weight:800;line-height:1.45;',
  h4: 'margin:12px 0 8px;color:#0f172a;font-size:15px;font-weight:700;line-height:1.5;',
  a: 'color:#2563eb;text-decoration:none;word-break:break-all;',
  img: 'max-width:100%;width:100%;height:auto;border-radius:12px;display:block;',
}
</script>

<template>
  <view class="ai-rich-content">
    <mp-html
      v-if="renderedHtml"
      :content="renderedHtml"
      :selectable="selectable"
      :scroll-table="true"
      :preview-img="true"
      :copy-link="false"
      :tag-style="tagStyle"
    />
  </view>
</template>

<style scoped lang="scss">
.ai-rich-content {
  width: 100%;
  min-width: 0;
}

.ai-rich-content :deep(.ai-code-block) {
  margin: 12px 0;
  padding: 14px 16px;
  border: 1px solid #1e293b;
  border-radius: 14px;
  background: #0f172a;
  box-sizing: border-box;
  overflow-x: auto;
}

.ai-rich-content :deep(.ai-code-block code) {
  display: block;
  font-size: 12px;
  line-height: 1.8;
  color: #e2e8f0;
  word-break: break-word;
  white-space: pre;
}

.ai-rich-content :deep(.hljs-comment),
.ai-rich-content :deep(.hljs-quote) {
  color: #94a3b8;
}

.ai-rich-content :deep(.hljs-keyword),
.ai-rich-content :deep(.hljs-selector-tag),
.ai-rich-content :deep(.hljs-literal),
.ai-rich-content :deep(.hljs-section),
.ai-rich-content :deep(.hljs-link) {
  color: #f472b6;
}

.ai-rich-content :deep(.hljs-string),
.ai-rich-content :deep(.hljs-title),
.ai-rich-content :deep(.hljs-name),
.ai-rich-content :deep(.hljs-attribute),
.ai-rich-content :deep(.hljs-symbol),
.ai-rich-content :deep(.hljs-bullet),
.ai-rich-content :deep(.hljs-addition) {
  color: #86efac;
}

.ai-rich-content :deep(.hljs-number),
.ai-rich-content :deep(.hljs-built_in),
.ai-rich-content :deep(.hljs-builtin-name),
.ai-rich-content :deep(.hljs-type),
.ai-rich-content :deep(.hljs-variable),
.ai-rich-content :deep(.hljs-template-variable) {
  color: #fbbf24;
}

.ai-rich-content :deep(.hljs-title.class_),
.ai-rich-content :deep(.hljs-class .hljs-title),
.ai-rich-content :deep(.hljs-function .hljs-title),
.ai-rich-content :deep(.hljs-params) {
  color: #93c5fd;
}

.ai-rich-content :deep(.hljs-emphasis) {
  font-style: italic;
}

.ai-rich-content :deep(.hljs-strong) {
  font-weight: 700;
}
</style>
