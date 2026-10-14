import { UnifiedPaper, RenderTypographySettings } from '../types'
import { adaptHuatuPaper } from './index'

/**
 * 华图在线通用主动嗅探器与官方接口请求器
 * 自动感知当前页面、提取 practiceId/paperId，并组装两步网络请求
 */
export async function fetchHuatuPaperActively(settings: RenderTypographySettings): Promise<UnifiedPaper | null> {
  const href = location.href
  console.log('[华图主动嗅探] 正在即时感知当前页面:', href)

  // 1. 从当前 URL 或 Hash 中提取练习/试卷 ID
  let practiceId: string | undefined = undefined

  const matchPractice = href.match(/\/practices?\/(\d+)/i)
  const matchExam = href.match(/\/exam\/[^\/]+\/(\d+)/i)
  const matchDetail = href.match(/\/detail\/(\d+)/i)
  const matchQuery = href.match(/[?&](?:id|practiceId|paperId|idList)=(\d+)/i)

  practiceId = matchPractice?.[1] || matchExam?.[1] || matchDetail?.[1] || matchQuery?.[1]

  // 2. 从 Performance 资源列表中嗅探最新接口或提取 ID
  let latestToken: string | undefined = undefined
  let latestPracticeUrl: string | undefined = undefined

  try {
    const resources = performance.getEntriesByType('resource')
    const practiceEntries = resources.filter((r) => {
      const name = r.name.toLowerCase()
      return name.includes('/p/v1/practices/') || name.includes('/q/v4/questions')
    })

    if (practiceEntries.length > 0) {
      const lastEntry = practiceEntries[practiceEntries.length - 1]
      latestPracticeUrl = lastEntry.name

      // 若未从 URL 提取出 ID，尝试从 performance 接口地址提取
      if (!practiceId) {
        const entryMatch = lastEntry.name.match(/\/p\/v1\/practices\/(\d+)/)
        if (entryMatch) {
          practiceId = entryMatch[1]
        }
      }
    }
  } catch (err) {
    console.warn('[华图主动嗅探] 读取 Performance 失败:', err)
  }

  console.log('[华图主动嗅探] 识别到当前华图练习标识:', practiceId || '(未识别到成套ID)')

  if (!practiceId) {
    return null
  }

  // 3. 发送官方请求拉取试卷详情
  try {
    const headers: Record<string, string> = {
      Accept: 'application/json, text/plain, */*',
      'Content-Type': 'application/json',
    }

    // 尝试从 cookie 或 localStorage 提取 token
    try {
      const tokenInLocal = localStorage.getItem('token') || localStorage.getItem('huatu_token')
      if (tokenInLocal) {
        headers['token'] = tokenInLocal
      }
    } catch {}

    // 第一步：拉取练习/试卷结构信息
    const practiceResp = await fetch(`https://ns.huatu.com/p/v1/practices/${practiceId}`, {
      method: 'GET',
      headers,
      credentials: 'include',
    })

    if (!practiceResp.ok) {
      console.warn('[华图主动嗅探] 请求 practices 失败，状态码:', practiceResp.status)
      return null
    }

    const practiceJson = await practiceResp.json()
    const practiceData = practiceJson.data || practiceJson

    const questionIds: (number | string)[] = practiceData.questions || []
    if (!Array.isArray(questionIds) || questionIds.length === 0) {
      console.warn('[华图主动嗅探] 练习中无题目 ID 列表')
      return null
    }

    // 第二步：批量拉取题目实体（支持分批拉取以防超长 URL，每批 50 道）
    const batchSize = 50
    let allSingleQuestions: any[] = []
    let allCompositeQuestions: any[] = []

    for (let i = 0; i < questionIds.length; i += batchSize) {
      const chunk = questionIds.slice(i, i + batchSize)
      const qUrl = `https://ns.huatu.com/q/v4/questions?ids=${chunk.join(',')}&terminal=3&appType=2`

      const qResp = await fetch(qUrl, {
        method: 'GET',
        headers,
        credentials: 'include',
      })

      if (qResp.ok) {
        const qJson = await qResp.json()
        const qData = qJson.data || qJson
        if (Array.isArray(qData.singleQuestions)) {
          allSingleQuestions.push(...qData.singleQuestions)
        }
        if (Array.isArray(qData.compositeQuestions)) {
          allCompositeQuestions.push(...qData.compositeQuestions)
        }
      }
    }

    // 组合为统一原始对象供适配器清洗归一化
    const rawCombined = {
      ...practiceData,
      singleQuestions: allSingleQuestions,
      compositeQuestions: allCompositeQuestions,
    }

    return adaptHuatuPaper(rawCombined, settings)
  } catch (err) {
    console.error('[华图主动嗅探] 发送网络请求异常:', err)
    return null
  }
}
