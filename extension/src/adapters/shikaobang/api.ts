import { UnifiedPaper, RenderTypographySettings } from '../types'
import { adaptShikaobangPaper } from './index'

/**
 * 事考帮通用主动嗅探器与官方只读接口请求器
 * 自动感知当前页面、提取 paper_id / 练习参数，发起只读获取
 */
export async function fetchShikaobangPaperActively(settings: RenderTypographySettings): Promise<UnifiedPaper | null> {
  const href = location.href
  console.log('[事考帮主动嗅探] 正在即时感知当前页面:', href)

  // 1. 尝试从当前 URL 提取参数
  let paperId: string | undefined = undefined
  const matchPaper = href.match(/[?&]paper_id=(\d+)/i)
  if (matchPaper) {
    paperId = matchPaper[1]
  }

  // 2. 从 Performance 资源列表中嗅探最新接口或提取 ID
  try {
    const resources = performance.getEntriesByType('resource')
    const skbEntries = resources.filter((r) => {
      const name = r.name.toLowerCase()
      return name.includes('/waapi/practiceexam/getpapercontent') || name.includes('/waapi/exercise/get-question')
    })

    if (skbEntries.length > 0) {
      const lastEntry = skbEntries[skbEntries.length - 1]
      if (!paperId) {
        const entryMatch = lastEntry.name.match(/[?&]paper_id=(\d+)/)
        if (entryMatch) {
          paperId = entryMatch[1]
        }
      }
    }
  } catch (err) {
    console.warn('[事考帮主动嗅探] 读取 Performance 失败:', err)
  }

  // 场景 A: 试卷场景 (含 paper_id)
  if (paperId) {
    try {
      const headers: Record<string, string> = {
        Accept: 'application/json, text/plain, */*',
        'Content-Type': 'application/json;charset=UTF-8',
      }

      // 尝试携带 token
      try {
        const token = localStorage.getItem('web_user_token') || localStorage.getItem('token')
        if (token) {
          headers['authorization'] = `Bearer ${token}`
        }
      } catch {}

      const resp = await fetch('https://www.shikaobang.cn/waapi/practiceexam/getPaperContent', {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify({
          paper_id: Number(paperId),
          type: 2,
          purpose: 'app',
          class_no: '',
        }),
      })

      if (resp.ok) {
        const json = await resp.json()
        if (json.status === 1 && json.data) {
          return adaptShikaobangPaper(json.data, settings)
        }
      }
    } catch (err) {
      console.warn('[事考帮主动嗅探] 试卷接口请求失败:', err)
    }
  }

  // 场景 B: 练习/错题场景 (从 URL 查询参数中提取)
  const urlObj = new URL(href)
  const mode = urlObj.searchParams.get('mode')
  const no = urlObj.searchParams.get('no')
  const exam = urlObj.searchParams.get('exam')
  const subject = urlObj.searchParams.get('subject')

  if (no && exam) {
    try {
      const headers: Record<string, string> = {
        Accept: 'application/json, text/plain, */*',
        'Content-Type': 'application/json;charset=UTF-8',
      }
      try {
        const token = localStorage.getItem('web_user_token') || localStorage.getItem('token')
        if (token) {
          headers['authorization'] = `Bearer ${token}`
        }
      } catch {}

      const reqBody: Record<string, any> = {
        source: urlObj.searchParams.get('source') || 'structure',
        no,
        exam,
        subject: subject || 'subject173',
        brand: urlObj.searchParams.get('brand') || 'skb',
        province: urlObj.searchParams.get('province') || 'zhejiang',
      }

      if (mode) reqBody.mode = mode
      if (urlObj.searchParams.get('wrong_mode')) {
        reqBody.wrong_mode = Number(urlObj.searchParams.get('wrong_mode'))
      }

      const resp = await fetch('https://www.shikaobang.cn/waapi/exercise/get-question', {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify(reqBody),
      })

      if (resp.ok) {
        const json = await resp.json()
        if (json.status === 1 && json.data) {
          return adaptShikaobangPaper(json.data, settings)
        }
      }
    } catch (err) {
      console.warn('[事考帮主动嗅探] 练习接口请求失败:', err)
    }
  }

  return null
}
