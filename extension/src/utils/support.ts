import { getAuthSession, getRequestAuthSession, isTokenExpired, requestAuthApi } from './auth'

const TYPES = ['bug', 'content_error', 'feature_request', 'product_suggestion', 'experience', 'other']

export async function submitExtensionFeedback(input: unknown): Promise<{ anonymous: boolean; accountChanged: boolean }> {
  const value = input as Record<string, unknown> | null
  if (!value || typeof value.content !== 'string' || !value.content.trim() || value.content.length > 500)
    throw new Error('请填写1至500字的反馈内容')
  if (typeof value.feedbackType !== 'string' || !TYPES.includes(value.feedbackType))
    throw new Error('请选择有效的反馈类型')
  if (value.contact !== undefined && (typeof value.contact !== 'string' || value.contact.length > 100))
    throw new Error('联系方式最多100字')
  const before = await getAuthSession()
  const session = await getRequestAuthSession()
  if (before.token && !session.token) throw new Error('登录已失效，请重新登录后提交，或明确退出登录后匿名反馈')
  if (session.token && isTokenExpired(session.token)) throw new Error('登录已过期，请重新登录后提交')
  await requestAuthApi('/feedbacks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(session.token ? { Authorization: `Bearer ${session.token.access_token}` } : {}) },
    body: JSON.stringify({
      feedback_type: value.feedbackType, content: value.content.trim(), contact: (value.contact as string || '').trim() || undefined,
      source_app: 'gongkao_extension', source_platform: 'chrome-extension',
      target_type: 'extension', target_id: chrome.runtime.getManifest().version,
    }),
  })
  // 提交已成功；后续本地存储读取失败也不能误报提交失败，诱导重复提交。
  const accountChanged = await getAuthSession()
    .then(current => current.token?.access_token !== session.token?.access_token)
    .catch(() => true)
  return { anonymous: !session.token, accountChanged }
}

export async function listExtensionFeedback(page: unknown) {
  if (!Number.isInteger(page) || Number(page) < 1 || Number(page) > 10000) throw new Error('反馈记录页码无效')
  const session = await getRequestAuthSession()
  const token = session.token?.access_token
  if (!token || isTokenExpired(session.token)) throw new Error('请先在插件弹窗登录，再查看反馈记录')
  const result = await requestAuthApi<{ items: unknown[]; total: number }>(`/feedbacks/mine?page=${page}&size=10`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if ((await getAuthSession()).token?.access_token !== token) throw new Error('账号已变化，请重新加载记录')
  if (!Array.isArray(result?.items) || typeof result.total !== 'number') throw new Error('反馈记录响应异常，请重试')
  return result
}
