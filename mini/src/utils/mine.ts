import dayjs from 'dayjs'

export function formatDateTime(value?: string | null, pattern = 'MM-DD HH:mm') {
  if (!value) {
    return '--'
  }

  const date = dayjs(value)
  return date.isValid() ? date.format(pattern) : value
}

export function formatDuration(totalSeconds?: number | null) {
  const seconds = Number(totalSeconds || 0)
  if (seconds <= 0) {
    return '0秒'
  }

  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainSeconds = seconds % 60

  if (hours > 0) {
    return `${hours}小时${minutes}分钟`
  }

  if (minutes > 0) {
    return `${minutes}分钟${remainSeconds > 0 ? `${remainSeconds}秒` : ''}`
  }

  return `${remainSeconds}秒`
}

export function stripRichText(value?: string | null) {
  return (value || '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function getSessionTypeLabel(type?: string | null) {
  const labelMap: Record<string, string> = {
    bank: '题库练习',
    chapter: '章节练习',
    random: '随机练习',
    exam: '模拟考试',
    wrong: '错题重练',
    favorite: '收藏重练',
  }

  return labelMap[type || ''] || '刷题练习'
}

export function getSessionStatusLabel(status?: string | null) {
  const labelMap: Record<string, string> = {
    completed: '已完成',
    in_progress: '进行中',
    abandoned: '已放弃',
  }

  return labelMap[status || ''] || '未知状态'
}

export function getQuestionTypeLabel(type?: string | null) {
  const labelMap: Record<string, string> = {
    single: '单选题',
    multiple: '多选题',
    judgement: '判断题',
    fill: '填空题',
    shortAnswer: '简答题',
  }

  return labelMap[type || ''] || '题目'
}

export function getDifficultyLabel(value?: string | null) {
  const labelMap: Record<string, string> = {
    easy: '简单',
    medium: '中等',
    hard: '困难',
  }

  return labelMap[value || ''] || '未标记'
}

export function toQuestionList(result: any) {
  if (Array.isArray(result)) {
    return result
  }

  return Array.isArray(result?.items) ? result.items : []
}
