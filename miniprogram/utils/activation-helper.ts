/**
 * 激活码工具函数
 */

/**
 * 从文本中提取激活码
 *
 * 支持的激活码格式：
 * - 标准格式：XXXXX-XXXXX-XXXXX（带或不带校验位）
 * - 带前后缀：PREFIX-XXXXX-XXXXX-XXXXX-SUFFIX
 *
 * :param text: 包含激活码的文本
 * :return: 提取到的激活码，如果没有找到则返回空字符串
 */
export function extractActivationCode(text: string): string {
  if (!text || !text.trim()) {
    return ''
  }

  // 激活码正则：匹配由字母、数字组成，用 - 分隔的字符串
  // 至少包含 2 个分组，每组至少 3 个字符
  const codePattern = /[A-Z0-9]{3,}(?:-[A-Z0-9]{3,}){1,}/gi
  const matches = text.match(codePattern)

  if (matches && matches.length > 0) {
    // 返回第一个匹配的激活码（转为大写）
    return matches[0].toUpperCase()
  }

  return ''
}

/**
 * 验证激活码格式
 *
 * :param code: 激活码
 * :return: 是否为有效格式
 */
export function validateActivationCodeFormat(code: string): boolean {
  if (!code || !code.trim()) {
    return false
  }

  // 激活码至少包含 2 个分组，每组 3-8 个字符
  const pattern = /^[A-Z0-9]{3,8}(?:-[A-Z0-9]{3,8}){1,}$/i
  return pattern.test(code.trim())
}
