/**
 * 验证工具函数
 */

/**
 * 验证手机号
 *
 * @param phone 手机号
 * @return 是否有效
 */
export function validatePhone(phone: string): boolean {
  return /^1[3-9]\d{9}$/.test(phone)
}

/**
 * 验证邮箱
 *
 * @param email 邮箱
 * @return 是否有效
 */
export function validateEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

/**
 * 验证身份证号
 *
 * @param idCard 身份证号
 * @return 是否有效
 */
export function validateIdCard(idCard: string): boolean {
  return /^[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[0-9Xx]$/.test(idCard)
}

/**
 * 验证 URL
 *
 * @param url URL地址
 * @return 是否有效
 */
export function validateUrl(url: string): boolean {
  try {
    new URL(url)
    return true
  } catch {
    return false
  }
}

/**
 * 验证密码强度
 *
 * @param password 密码
 * @return 强度等级 0=弱 1=中 2=强
 */
export function validatePasswordStrength(password: string): 0 | 1 | 2 {
  if (password.length < 6) return 0

  const hasLetter = /[a-zA-Z]/.test(password)
  const hasNumber = /\d/.test(password)
  const hasSpecial = /[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(password)

  const score = [hasLetter, hasNumber, hasSpecial].filter(Boolean).length

  if (score >= 3 && password.length >= 8) return 2
  if (score >= 2) return 1
  return 0
}

/**
 * 验证是否为空
 *
 * @param value 值
 * @return 是否为空
 */
export function isEmpty(value: any): boolean {
  if (value === null || value === undefined) return true
  if (typeof value === 'string') return value.trim() === ''
  if (Array.isArray(value)) return value.length === 0
  if (typeof value === 'object') return Object.keys(value).length === 0
  return false
}
