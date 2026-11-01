import './support.css'
import { exportMessage } from '../utils/export-flow'

const element = <T extends HTMLElement>(id: string) => document.getElementById(id) as T
element('version').textContent = `v ${chrome.runtime.getManifest().version}`
const form = element<HTMLFormElement>('feedback-form')
const content = element<HTMLTextAreaElement>('content')
const contact = element<HTMLInputElement>('contact')
const submit = element<HTMLButtonElement>('submit')
const status = element('submit-status')
const historyStatus = element('history-status')
const historyList = element('history-list')
const previous = element<HTMLButtonElement>('previous')
const next = element<HTMLButtonElement>('next')
const refresh = element<HTMLButtonElement>('load-history')
let page = 1
let historyVersion = 0

content.addEventListener('input', () => { element('content-count').textContent = `${content.value.length} / 500` })
form.addEventListener('submit', async event => {
  event.preventDefault()
  if (submit.disabled) return
  if (!content.value.trim()) { status.textContent = '请填写反馈内容'; content.focus(); return }
  submit.disabled = true
  content.disabled = true
  contact.disabled = true
  element<HTMLSelectElement>('feedback-type').disabled = true
  status.textContent = '正在提交，请勿重复操作…'
  try {
    const result = await exportMessage('SUBMIT_FEEDBACK', {
      feedbackType: element<HTMLSelectElement>('feedback-type').value, content: content.value, contact: contact.value,
    })
    form.reset()
    element('content-count').textContent = '0 / 500'
    status.textContent = result.data?.accountChanged
      ? '反馈已提交，但账户已变化；该记录归提交时的账号（匿名提交不关联账号）。'
      : result.data?.anonymous
      ? '匿名反馈已提交。若填写了联系方式，请留意后续联系；此条不关联账号记录。'
      : '反馈已提交，可在下方“我的反馈”查看处理回复。'
  } catch (error: any) {
    status.textContent = `${error?.message || '提交失败'}。内容已保留；网络超时时请先查看记录，避免重复提交。`
  } finally {
    submit.disabled = false
    content.disabled = false
    contact.disabled = false
    element<HTMLSelectElement>('feedback-type').disabled = false
  }
})

const statusLabels: Record<string, string> = { pending: '待处理', processing: '处理中', resolved: '已解决', rejected: '已关闭' }
async function loadHistory(targetPage = 1) {
  const version = ++historyVersion
  refresh.disabled = true
  previous.disabled = true
  next.disabled = true
  historyList.replaceChildren()
  historyStatus.textContent = '正在加载…'
  try {
    const { data } = await exportMessage('LIST_FEEDBACK', { page: targetPage })
    if (version !== historyVersion) return
    for (const record of data.items) {
      const article = document.createElement('article')
      article.className = 'feedback-item'
      for (const [text, className] of [
        [`${statusLabels[record.status] || '状态未知'} · ${String(record.created_time || '')}`, ''],
        [record.content || '', ''],
        [record.reply_content ? `处理回复：${record.reply_content}` : '暂无处理回复', 'reply'],
      ]) {
        const paragraph = document.createElement('p')
        paragraph.textContent = String(text)
        paragraph.className = className
        article.append(paragraph)
      }
      historyList.append(article)
    }
    page = targetPage
    historyStatus.textContent = data.items.length ? `共 ${data.total} 条反馈` : '当前账号暂无反馈记录'
    element('page-label').textContent = `第 ${page} 页`
    previous.disabled = page <= 1
    next.disabled = page * 10 >= data.total
  } catch (error: any) {
    if (version === historyVersion) { historyStatus.textContent = error?.message || '加载失败，请重试'; element('page-label').textContent = '' }
  } finally { if (version === historyVersion) refresh.disabled = false }
}
refresh.addEventListener('click', () => { void loadHistory() })
previous.addEventListener('click', () => { void loadHistory(page - 1) })
next.addEventListener('click', () => { void loadHistory(page + 1) })
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === 'local' && ('fba_auth_token' in changes || 'fba_auth_user' in changes)) {
    historyVersion++
    historyList.replaceChildren()
    historyStatus.textContent = '账户信息已变化，请重新加载反馈记录'
    refresh.disabled = false
    previous.disabled = true
    next.disabled = true
  }
})
