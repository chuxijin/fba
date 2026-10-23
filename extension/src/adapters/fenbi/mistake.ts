import { UnifiedPaper, UnifiedQuestion, RenderTypographySettings, MistakePageMeta } from '../types'
import { extractFenbiPaperFromDom } from './dom'
import { normalizeFenbiQuestion, formatFenbiPaperTitle } from './normalize'

/** 全局错题考点树内存缓存 */
let cachedKeypointTree: any = null
/** 当前激活的题库分类代码 (如 xingce, syzc, jiaoshi 等，随拦截和路由自适应更新) */
let activeTikuPrefix: string = 'xingce'

export function setActiveTikuPrefix(prefix: string) {
  if (prefix && typeof prefix === 'string') {
    activeTikuPrefix = prefix.toLowerCase()
    try {
      ;(window as any).__FENBI_ACTIVE_TIKU_PREFIX__ = activeTikuPrefix
    } catch {}
  }
}

export function getActiveTikuPrefix(): string {
  try {
    if ((window as any).__FENBI_ACTIVE_TIKU_PREFIX__) {
      return (window as any).__FENBI_ACTIVE_TIKU_PREFIX__
    }
  } catch {}
  return activeTikuPrefix || 'xingce'
}

export function setCachedKeypointTree(tree: any) {
  if (tree) {
    cachedKeypointTree = tree
    try {
      ;(window as any).__FENBI_KEYPOINT_TREE__ = tree
    } catch {}
  }
}

export function getCachedKeypointTree(): any {
  if (cachedKeypointTree) return cachedKeypointTree
  try {
    if ((window as any).__FENBI_KEYPOINT_TREE__) {
      cachedKeypointTree = (window as any).__FENBI_KEYPOINT_TREE__
      return cachedKeypointTree
    }
  } catch {}
  return null
}

export function getGlobalSolutionsPool(): Map<number, any> {
  try {
    if ((window as any).__FENBI_GLOBAL_SOLUTIONS_MAP__ instanceof Map) {
      return (window as any).__FENBI_GLOBAL_SOLUTIONS_MAP__
    }
  } catch {}
  return new Map()
}

export function getGlobalCapturedQuestionIds(): number[] {
  try {
    if (Array.isArray((window as any).__FENBI_CAPTURED_QUESTION_IDS__)) {
      return (window as any).__FENBI_CAPTURED_QUESTION_IDS__
    }
  } catch {}
  return []
}

/**
 * 从页面当前 URL 智能提取错题知识点页面元数据
 */
export function parseMistakePageMeta(url: string, pageTitle: string = ''): MistakePageMeta | null {
  if (!url || (!url.includes('/error/') && !url.includes('/errors/'))) {
    return null
  }

  try {
    const urlObj = new URL(url)
    const params = urlObj.searchParams
    const totalStr = params.get('total')
    const total = totalStr ? parseInt(totalStr, 10) : 0

    // 路径特征: .../practice/{category}/{category}/{keypointId}/{page}
    const pathParts = urlObj.pathname.split('/').filter(Boolean)
    let keypointId: string | undefined = undefined
    let currentPage = 1

    for (let i = 0; i < pathParts.length; i++) {
      const part = pathParts[i]
      if (i + 1 < pathParts.length && pathParts[i + 1] === part && !/^\d+$/.test(part)) {
        setActiveTikuPrefix(part)
        if (i + 2 < pathParts.length && /^\d+$/.test(pathParts[i + 2])) {
          keypointId = pathParts[i + 2]
          if (i + 3 < pathParts.length && /^\d+$/.test(pathParts[i + 3])) {
            currentPage = parseInt(pathParts[i + 3], 10)
          }
          break
        }
      } else if (/^\d+$/.test(part) && !keypointId) {
        if (i > 0 && !/^\d+$/.test(pathParts[i - 1])) {
          setActiveTikuPrefix(pathParts[i - 1])
        }
        keypointId = part
        if (i + 1 < pathParts.length && /^\d+$/.test(pathParts[i + 1])) {
          currentPage = parseInt(pathParts[i + 1], 10)
        }
        break
      }
    }

    if (!keypointId && params.get('keypointId')) {
      keypointId = params.get('keypointId')!
    }

    let keypointName = pageTitle.replace(/[-_].*$/, '').replace(/粉笔.*$/, '').trim()
    if (!keypointName || keypointName === '粉笔') {
      keypointName = '专项错题'
    }

    if (total > 0 || keypointId) {
      return {
        keypointId,
        keypointName,
        total: total > 0 ? total : 10,
        currentPage,
        pageSize: 10,
        order: params.get('order') || 'desc',
        timeRange: params.get('timeRange') || 0,
      }
    }
  } catch (e) {
  }

  return null
}

/**
 * 递归从考点树中定位指定 keypointId 的节点并提取全部 questionIds
 */
export function extractQuestionIdsByKeypoint(
  tree: any,
  targetKeypointId: string | number,
  fallbackName: string = ''
): { keypointName: string; questionIds: number[] } {
  const resultIds: number[] = []
  let foundName = ''

  if (!tree) return { keypointName: fallbackName, questionIds: resultIds }

  const root = tree.data || tree.datas || tree.tree || tree.keypoints || tree
  const targetStr = String(targetKeypointId)
  const cleanFallbackName = fallbackName.replace(/粉笔/g, '').replace(/错题/g, '').replace(/[-_].*$/, '').trim()

  function traverse(node: any): boolean {
    if (!node) return false
    const nodeId = String(node.id ?? node.keypointId ?? node.keyPointId ?? node.kpid ?? '')
    const nodeName = String(node.name || node.title || '')
    const isIdMatch = Boolean(targetStr && nodeId === targetStr)
    const isNameMatch = Boolean(cleanFallbackName && cleanFallbackName.length >= 2 && nodeName.includes(cleanFallbackName))

    if (isIdMatch || isNameMatch) {
      foundName = nodeName || fallbackName || ''
      collectIds(node)
      return true
    }

    if (Array.isArray(node.children)) {
      for (const child of node.children) {
        if (traverse(child)) return true
      }
    }
    if (Array.isArray(node)) {
      for (const item of node) {
        if (traverse(item)) return true
      }
    }
    return false
  }

  function collectIds(node: any) {
    if (!node) return
    const candidateArrays = [node.questionIds, node.questions, node.questionList, node.exerciseIds, node.ids]
    for (const arr of candidateArrays) {
      if (Array.isArray(arr)) {
        for (const item of arr) {
          const num = typeof item === 'object' ? Number(item?.id || item?.questionId) : Number(item)
          if (!isNaN(num) && num > 0) resultIds.push(num)
        }
      }
    }
    if (Array.isArray(node.children)) {
      for (const child of node.children) collectIds(child)
    }
  }

  traverse(root)

  if (resultIds.length === 0) {
    function collectAll(node: any) {
      if (!node) return
      collectIds(node)
      if (Array.isArray(node)) {
        for (const item of node) collectAll(item)
      }
    }
    collectAll(root)
  }

  return { keypointName: foundName || fallbackName, questionIds: Array.from(new Set(resultIds)) }
}

/**
 * 主动拉取错题知识点考点树
 */
export async function fetchKeypointTree(): Promise<any> {
  const cached = getCachedKeypointTree()
  if (cached) return cached

  const prefix = getActiveTikuPrefix()
  try {
    const url = `https://tiku.fenbi.com/api/${prefix}/errors/keypoint-tree?timeRange=0&order=desc&app=web&version=3.0.0.0`
    const res = await fetch(url, { credentials: 'include' })
    if (res.ok) {
      const data = await res.json()
      setCachedKeypointTree(data)
      return data
    }
  } catch (e) {
  }
  return null
}

/**
 * 探测考点专属错题列表接口 (多源探测)
 */
export async function fetchKeypointQuestionIdsActively(
  keypointId: string | number,
  targetCount: number = 100
): Promise<number[]> {
  const prefix = getActiveTikuPrefix()
  const candidateUrls = [
    `https://tiku.fenbi.com/api/${prefix}/errors/practice/${keypointId}?page=1&pageSize=${targetCount}&timeRange=0&order=desc&app=web&version=3.0.0.0`,
    `https://tiku.fenbi.com/api/${prefix}/errors/keypoints/${keypointId}?page=1&pageSize=${targetCount}&timeRange=0&order=desc&app=web&version=3.0.0.0`,
    `https://tiku.fenbi.com/api/${prefix}/errors/keypoints/${keypointId}/questions?page=1&pageSize=${targetCount}&timeRange=0&order=desc&app=web&version=3.0.0.0`,
    `https://tiku.fenbi.com/api/${prefix}/errors/list?keypointId=${keypointId}&page=1&pageSize=${targetCount}&timeRange=0&order=desc&app=web&version=3.0.0.0`,
  ]

  for (const url of candidateUrls) {
    try {
      const res = await fetch(url, { credentials: 'include' })
      if (res.ok) {
        const json = await res.json()
        const found: number[] = []
        const list = Array.isArray(json)
          ? json
          : json?.questionIds || json?.ids || json?.questions || json?.exercises || json?.datas || json?.data
        if (Array.isArray(list)) {
          for (const item of list) {
            const num = typeof item === 'object' ? Number(item?.id || item?.questionId) : Number(item)
            if (!isNaN(num) && num > 0) found.push(num)
          }
        }
        if (found.length > 0) {
          return Array.from(new Set(found))
        }
      }
    } catch {}
  }
  return []
}

/**
 * 自动巡检触发当前错题单页应用分页加载，使拦截器截获全量数据
 */
export async function harvestMistakePagesIfNeed(neededCount: number): Promise<void> {
  if (typeof document === 'undefined') return
  const pool = getGlobalSolutionsPool()
  if (pool.size >= neededCount) return

  const paginationItems = Array.from(
    document.querySelectorAll(
      '.ant-pagination-item, .pagination li, [class*="pagination"] button, [class*="pagination"] li'
    )
  ) as HTMLElement[]

  if (paginationItems.length === 0) return

  const activeItem = paginationItems.find((el) => el.classList.contains('ant-pagination-item-active'))
  const activePage = activeItem?.textContent?.trim()

  const pageButtons = paginationItems.filter((el) => {
    const txt = el.textContent?.trim()
    return txt && /^\d+$/.test(txt) && !el.classList.contains('ant-pagination-item-active')
  })

  for (const btn of pageButtons) {
    if (getGlobalSolutionsPool().size >= neededCount) break
    btn.click()
    await new Promise((r) => setTimeout(r, 200))
  }

  // 恢复原始页
  if (activePage) {
    const restoreBtn = paginationItems.find((el) => el.textContent?.trim() === activePage)
    restoreBtn?.click()
    await new Promise((r) => setTimeout(r, 100))
  }
}

/**
 * 按照用户指定数量 (如 10/20/30/50/全部) 聚合错题、名师解析与真题来源，汇编为完整 UnifiedPaper
 */
export async function fetchMistakeQuestionsByCount(options: {
  keypointId?: string | number
  keypointName?: string
  targetCount: number
  settings: RenderTypographySettings
  onProgress?: (loaded: number, total: number) => void
}): Promise<UnifiedPaper> {
  const { keypointId, keypointName = '专项错题', targetCount, settings, onProgress } = options

  let questionIds: number[] = []
  let detectedName = keypointName

  // 1. 考点树中定位
  const tree = await fetchKeypointTree()
  if (tree && keypointId) {
    const extracted = extractQuestionIdsByKeypoint(tree, keypointId, detectedName)
    if (extracted.questionIds.length > 0) questionIds = extracted.questionIds
    if (extracted.keypointName) detectedName = extracted.keypointName
  }

  // 2. 考点专属接口主动探测
  if (questionIds.length < targetCount && keypointId) {
    const activeIds = await fetchKeypointQuestionIdsActively(keypointId, Math.max(targetCount, 100))
    if (activeIds.length > 0) {
      questionIds = Array.from(new Set([...questionIds, ...activeIds]))
    }
  }

  // 3. 截获池与 DOM 兜底搜集
  const capturedIds = getGlobalCapturedQuestionIds()
  if (capturedIds.length > 0) {
    questionIds = Array.from(new Set([...questionIds, ...capturedIds]))
  }

  if (questionIds.length < targetCount && typeof document !== 'undefined') {
    const domQEls = document.querySelectorAll(
      '[data-question-id], [data-id], .exercise-item, .question-item, .solution-item, .wrong-item, .error-item'
    )
    domQEls.forEach((el) => {
      const qid = el.getAttribute('data-question-id') || el.getAttribute('data-id')
      if (qid && /^\d+$/.test(qid)) questionIds.push(Number(qid))
    })
    questionIds = Array.from(new Set(questionIds))
  }

  // 4. 若收集数量依然少于用户期望，触发轻量快速跨页嗅探
  if (questionIds.length < targetCount) {
    await harvestMistakePagesIfNeed(targetCount)
    const afterHarvestIds = getGlobalCapturedQuestionIds()
    if (afterHarvestIds.length > 0) {
      questionIds = Array.from(new Set([...questionIds, ...afterHarvestIds]))
    }
  }

  const targetIds = questionIds.slice(0, targetCount)

  // 5. 准备题目映射：优先复用全局池中已截获的试题
  const solMap = new Map<number, any>()
  const globalPool = getGlobalSolutionsPool()
  for (const [qid, sol] of globalPool.entries()) {
    solMap.set(qid, sol)
  }

  const idsToFetch = targetIds.filter((id) => !solMap.has(id))
  const prefix = getActiveTikuPrefix()
  const chunkSize = 20
  const chunks: number[][] = []
  for (let i = 0; i < idsToFetch.length; i += chunkSize) {
    chunks.push(idsToFetch.slice(i, i + chunkSize))
  }

  let loadedCount = targetIds.length - idsToFetch.length
  if (onProgress) onProgress(Math.min(loadedCount, targetCount), targetCount)

  for (const chunk of chunks) {
    try {
      const apiUrl = `https://tiku.fenbi.com/api/${prefix}/universal/auth/solutions?type=1&questionIds=${chunk.join(',')}&app=web&version=3.0.0.0`
      const res = await fetch(apiUrl, { credentials: 'include' })
      if (res.ok) {
        const json = await res.json()
        const qList = Array.isArray(json)
          ? json
          : Array.isArray(json.solutions)
          ? json.solutions
          : Array.isArray(json.questions)
          ? json.questions
          : typeof json === 'object'
          ? Object.values(json).filter((v: any) => v && (v.content || v.stem || v.id))
          : []

        for (const sol of qList) {
          const qid = Number(sol.id || sol.questionId || sol.globalId)
          if (qid) {
            solMap.set(qid, sol)
            try {
              if ((window as any).__FENBI_GLOBAL_SOLUTIONS_MAP__ instanceof Map) {
                ;(window as any).__FENBI_GLOBAL_SOLUTIONS_MAP__.set(qid, sol)
              }
            } catch {}
          }
        }
        loadedCount += chunk.length
        if (onProgress) onProgress(Math.min(loadedCount, targetCount), targetCount)
      }
    } catch (e) {
    }
  }

  // 6. 统一使用 normalizeFenbiQuestion 清洗组装题目 (DRY 原则)
  const unifiedQuestions: UnifiedQuestion[] = []
  let order = 1
  const exportIds = targetIds.length > 0 ? targetIds : Array.from(solMap.keys()).slice(0, targetCount)

  for (const qid of exportIds) {
    const rawQ = solMap.get(qid)
    if (!rawQ) continue
    unifiedQuestions.push(
      normalizeFenbiQuestion(rawQ, order++, settings, undefined, `${detectedName} 错题集训`)
    )
  }

  // 7. 兜底与规范标题
  if (unifiedQuestions.length === 0 && typeof document !== 'undefined') {
    const domPaper = extractFenbiPaperFromDom(settings)
    if (domPaper && domPaper.sections && domPaper.sections.length > 0 && domPaper.total_questions > 0) {
      return domPaper
    }
  }

  const cleanKpName = detectedName.replace(/粉笔/g, '').replace(/错题/g, '').replace(/[-_].*$/, '').trim() || '专项'
  const finalTitle = formatFenbiPaperTitle(detectedName, true, cleanKpName)

  return {
    title: finalTitle,
    source_platform: 'fenbi',
    total_questions: unifiedQuestions.length,
    sections: [
      {
        name: `${cleanKpName}错题集训`,
        description: '请在答题卡规定区域内作答，每小题有且仅有一个正确答案。',
        questions: unifiedQuestions,
      },
    ],
    metadata: {
      scene: 'mistake',
      hasAnswers: true,
      keypointId,
      keypointName: cleanKpName,
      created_at: new Date().toISOString(),
    },
  }
}
