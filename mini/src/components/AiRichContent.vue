<script lang="ts" setup>
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

function isTableDivider(value: string) {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(value)
}

function isTableRow(value: string) {
  return value.includes('|') && !isTableDivider(value)
}

function isUnorderedList(value: string) {
  return /^\s*[-*+]\s+/.test(value)
}

function isOrderedList(value: string) {
  return /^\s*\d+\.\s+/.test(value)
}

function isBlockBoundary(value: string) {
  return !value.trim()
    || /^\s*(```|~~~)/.test(value)
    || /^\s{0,3}#{1,6}\s+/.test(value)
    || /^\s*>/.test(value)
    || isUnorderedList(value)
    || isOrderedList(value)
    || isTableRow(value)
}

function renderInlineMarkdown(value: string) {
  let nextValue = escapeHtml(value)
  const tokens: string[] = []
  const stashHtml = (html: string) => {
    const token = `@@AI_HTML_TOKEN_${tokens.length}@@`
    tokens.push(html)
    return token
  }

  nextValue = nextValue.replace(
    /`([^`]+)`/g,
    (_, code: string) => stashHtml(`<code class="ai-inline-code">${code}</code>`),
  )
  nextValue = nextValue.replace(
    /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
    (_, label: string, url: string) => stashHtml(`<a href="${url}">${label}</a>`),
  )

  nextValue = nextValue.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  nextValue = nextValue.replace(/__([^_]+)__/g, '<strong>$1</strong>')
  nextValue = nextValue.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  nextValue = nextValue.replace(/_([^_]+)_/g, '<em>$1</em>')
  nextValue = nextValue.replace(
    /(^|[\s>])(https?:\/\/[^\s<]+)/g,
    '$1<a href="$2">$2</a>',
  )

  return tokens.reduce((html, tokenHtml, index) => {
    return html.replace(`@@AI_HTML_TOKEN_${index}@@`, tokenHtml)
  }, nextValue)
}

function splitTableCells(value: string) {
  return value
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map(item => item.trim())
}

function renderTable(lines: string[], startIndex: number) {
  const headers = splitTableCells(lines[startIndex])
  const rows: string[][] = []
  let index = startIndex + 2

  while (index < lines.length && isTableRow(lines[index])) {
    rows.push(splitTableCells(lines[index]))
    index += 1
  }

  const headerHtml = headers
    .map(item => `<th>${renderInlineMarkdown(item)}</th>`)
    .join('')
  const rowsHtml = rows
    .map((row) => {
      const cellsHtml = row
        .map(item => `<td>${renderInlineMarkdown(item)}</td>`)
        .join('')
      return `<tr>${cellsHtml}</tr>`
    })
    .join('')

  return {
    html: `<table><thead><tr>${headerHtml}</tr></thead><tbody>${rowsHtml}</tbody></table>`,
    nextIndex: index,
  }
}

function renderList(lines: string[], startIndex: number, ordered: boolean) {
  const tag = ordered ? 'ol' : 'ul'
  const matcher = ordered ? /^\s*\d+\.\s+/ : /^\s*[-*+]\s+/
  const items: string[] = []
  let index = startIndex

  while (index < lines.length) {
    const line = lines[index]
    if (ordered && !isOrderedList(line)) {
      break
    }
    if (!ordered && !isUnorderedList(line)) {
      break
    }

    items.push(`<li>${renderInlineMarkdown(line.replace(matcher, '').trim())}</li>`)
    index += 1
  }

  return {
    html: `<${tag}>${items.join('')}</${tag}>`,
    nextIndex: index,
  }
}

function renderMarkdown(value: string) {
  const lines = value.replace(/\r\n/g, '\n').split('\n')
  const blocks: string[] = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index]
    const trimmed = line.trim()

    if (!trimmed) {
      index += 1
      continue
    }

    const fence = trimmed.match(/^(```|~~~)\s*(\w+)?/)
    if (fence) {
      const fenceMark = fence[1]
      const language = fence[2] || ''
      const codeLines: string[] = []
      index += 1

      while (index < lines.length && !lines[index].trim().startsWith(fenceMark)) {
        codeLines.push(lines[index])
        index += 1
      }

      if (index < lines.length) {
        index += 1
      }

      blocks.push(
        `<pre class="ai-code-block"><code class="ai-code-text${language ? ` language-${language}` : ''}">${escapeHtml(codeLines.join('\n'))}</code></pre>`,
      )
      continue
    }

    const heading = line.match(/^\s{0,3}(#{1,6})\s+(.+)$/)
    if (heading) {
      const level = Math.min(heading[1].length, 4)
      blocks.push(`<h${level}>${renderInlineMarkdown(heading[2].trim())}</h${level}>`)
      index += 1
      continue
    }

    if (trimmed.startsWith('>')) {
      const quoteLines: string[] = []
      while (index < lines.length && lines[index].trim().startsWith('>')) {
        quoteLines.push(lines[index].replace(/^\s*>\s?/, ''))
        index += 1
      }
      blocks.push(`<blockquote>${quoteLines.map(item => renderInlineMarkdown(item)).join('<br/>')}</blockquote>`)
      continue
    }

    if (isUnorderedList(line)) {
      const result = renderList(lines, index, false)
      blocks.push(result.html)
      index = result.nextIndex
      continue
    }

    if (isOrderedList(line)) {
      const result = renderList(lines, index, true)
      blocks.push(result.html)
      index = result.nextIndex
      continue
    }

    if (isTableRow(line) && index + 1 < lines.length && isTableDivider(lines[index + 1])) {
      const result = renderTable(lines, index)
      blocks.push(result.html)
      index = result.nextIndex
      continue
    }

    const paragraphLines: string[] = []
    while (index < lines.length && !isBlockBoundary(lines[index])) {
      paragraphLines.push(lines[index].trim())
      index += 1
    }

    if (paragraphLines.length > 0) {
      blocks.push(`<p>${paragraphLines.map(item => renderInlineMarkdown(item)).join('<br/>')}</p>`)
      continue
    }

    blocks.push(`<p>${renderInlineMarkdown(trimmed)}</p>`)
    index += 1
  }

  return blocks.join('')
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
    nextHtml = renderMarkdown(raw)
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

.ai-rich-content :deep(.ai-code-text) {
  display: block;
  font-size: 12px;
  line-height: 1.8;
  color: #e2e8f0;
  word-break: break-word;
  white-space: pre;
}
</style>
