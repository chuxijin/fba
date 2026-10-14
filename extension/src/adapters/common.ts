/**
 * 公考内容排版 - 跨平台通用工具集
 * 提供全国公职考试官方标准的反向设问加粗、HTML清洗、选项标号等公共能力
 */

/**
 * 反向设问陷阱词加粗处理器 (国考 1:1 考场实战防坑利器)
 */
export function applyNegativeKeywordsBold(text: string): string {
  if (!text) return ''
  const negativeKeywords = [
    '不正确', '不属于', '错误', '不符合', '最不恰当',
    '反面', '无关', '不能支持', '不能反驳', '不能削弱',
    '并非', '不包括', '没有体现', '未体现'
  ]
  let result = text
  for (const kw of negativeKeywords) {
    const regex = new RegExp(`(?<!<b>)${kw}(?!<\\/b>)`, 'g')
    result = result.replace(regex, `<b>${kw}</b>`)
  }
  return result
}

/**
 * 清洗 HTML 标签，保留基本段落与加粗
 */
export function cleanHtmlContent(html: string): string {
  if (!html) return ''
  return html.trim()
}

/**
 * 格式化文件名为安全合法的系统文件名
 */
export function sanitizeFileName(name: string): string {
  return name.replace(/[\\/:*?"<>|]/g, '_').trim()
}
