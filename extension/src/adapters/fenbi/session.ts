import { UnifiedPaper, RenderTypographySettings, DEFAULT_TYPOGRAPHY_SETTINGS } from '../types'
import { adaptFenbiPaper } from './index'

/**
 * 粉笔模考与试卷会话状态管理中心 (高内聚：全权管理双包聚合、答题卡解析与错题打标)
 */
class FenbiSessionManager {
  private staticPaper: any = null
  private staticPaperUrl: string = ''
  private answerSheet: any = null
  private wrongIds: Set<number> = new Set()
  private wrongKeys: Set<string> = new Set()
  private wrongOrders: Set<number> = new Set()
  private userAnswers: string[] = []
  private userAnswersMap: Map<string, string> = new Map()
  private currentAggregatedPaper: UnifiedPaper | null = null

  /**
   * 重置当前会话 (例如路由切换时)
   */
  public reset() {
    this.staticPaper = null
    this.staticPaperUrl = ''
    this.answerSheet = null
    this.wrongIds.clear()
    this.wrongKeys.clear()
    this.wrongOrders.clear()
    this.userAnswers = []
    this.userAnswersMap.clear()
    this.currentAggregatedPaper = null
  }

  /**
   * 获取当前已聚合的试卷 (若有)
   */
  public getPaper(): UnifiedPaper | null {
    return this.currentAggregatedPaper
  }

  /**
   * 处理粉笔相关的原始网络拦截数据包
   * 自动识别是【静态题包】还是【答题卡/成绩报告包 (getReport/getSolution)】，并自动实现双向聚合
   */
  public handleNetworkPayload(url: string, rawData: any, settings: RenderTypographySettings = DEFAULT_TYPOGRAPHY_SETTINGS): UnifiedPaper | null {
    if (!rawData) return null

    // 1. 无条件安全解包 { code: 1, data: { ... } }
    const payload = (rawData.data && typeof rawData.data === 'object' && !Array.isArray(rawData.data)) ? rawData.data : rawData

    const lowerUrl = url.toLowerCase()
    const isReportOrSolutionApi =
      lowerUrl.includes('/getreport') ||
      lowerUrl.includes('/getsolution') ||
      lowerUrl.includes('/report') ||
      lowerUrl.includes('/sheet')

    const hasSheetTraits = Boolean(
      payload.userAnswers ||
      payload.scores ||
      payload.answers ||
      payload.sheet?.userAnswers ||
      payload.sheet?.scores ||
      payload.sheet?.answers ||
      (payload.card && Array.isArray(payload.card.children))
    )

    // 检查是否具备题目内容 (questions / solutions / exercises)
    const rawQuestions = payload.questions || payload.solutions || payload.exercises
    const hasRealQuestions = Array.isArray(rawQuestions) && rawQuestions.length > 0

    // ==========================================
    // A. 答题卡 / 模考成绩报告包 (getReport / getSolution)
    // 纯粹静默捕获，100% 杜绝插件主动发起 fetch 请求
    // ==========================================
    if (isReportOrSolutionApi || (hasSheetTraits && !hasRealQuestions)) {
      this.answerSheet = payload
      this.parseAnswerSheet(payload)

      // 如果已有静态题包，立即打标并重新生成试卷
      if (this.staticPaper) {
        return this.buildAggregatedPaper(settings)
      }
      return null
    }

    // ==========================================
    // B. 试卷静态题包 (包含题干、选项、参考答案)
    // ==========================================
    if (hasRealQuestions) {
      this.staticPaper = payload
      this.staticPaperUrl = url
      return this.buildAggregatedPaper(settings)
    }

    return null
  }

  /**
   * 深入解析答题卡与成绩报告 (核心: 提取 state: -1 / State: -1 / status: -1 错题)
   */
  private parseAnswerSheet(sheetData: any) {
    if (!sheetData) return

    // 1. 提取考生作答与按题状态字典 (粉笔真实模考为 userAnswers: { "key": { id, status: -1, scoreRate: 0, answer: { choice: "0" } } })
    const rawUserAnswers = sheetData.userAnswers || sheetData.sheet?.userAnswers
    if (rawUserAnswers) {
      if (Array.isArray(rawUserAnswers)) {
        this.userAnswers = rawUserAnswers
      } else if (typeof rawUserAnswers === 'object') {
        for (const [k, item] of Object.entries(rawUserAnswers)) {
          if (!item || typeof item !== 'object') continue
          const keyStr = String((item as any).key || k || '')
          const idNum = Number((item as any).id || (item as any).questionId)
          const stateVal = (item as any).status !== undefined ? (item as any).status : (item as any).state
          const stateStr = String(stateVal)
          const scoreRate = (item as any).scoreRate
          const score = (item as any).score

          const isStateWrong =
            stateVal === -1 ||
            stateStr === '-1' ||
            (item as any).State === -1 ||
            String((item as any).State) === '-1' ||
            (item as any).Status === -1 ||
            String((item as any).Status) === '-1'

          const isScoreWrong = scoreRate === 0 || score === 0
          const isResultWrong =
            (item as any).result === 2 ||
            (item as any).result === -1 ||
            (item as any).isWrong === true ||
            (item as any).wrong === true

          if (isStateWrong || isScoreWrong || isResultWrong) {
            if (keyStr) this.wrongKeys.add(keyStr)
            if (idNum && !isNaN(idNum)) this.wrongIds.add(idNum)
          }

          if ((item as any).answer?.choice !== undefined) {
            const choiceStr = String((item as any).answer.choice)
            if (keyStr) this.userAnswersMap.set(keyStr, choiceStr)
            if (idNum) this.userAnswersMap.set(String(idNum), choiceStr)
          }
        }
      }
    }

    // 2. 提取 states / scores 扁平数组 (兼容单列数组结构)
    const rawStates = Array.isArray(sheetData.states) ? sheetData.states : (Array.isArray(sheetData.sheet?.states) ? sheetData.sheet.states : null)
    if (Array.isArray(rawStates) && rawStates.length > 0) {
      for (let i = 0; i < rawStates.length; i++) {
        const s = rawStates[i]
        if (s === -1 || String(s) === '-1') {
          this.wrongOrders.add(i + 1)
        }
      }
    }

    const scores = Array.isArray(sheetData.scores) ? sheetData.scores : sheetData.sheet?.scores
    if (Array.isArray(scores) && scores.length > 0) {
      for (let i = 0; i < scores.length; i++) {
        if (scores[i] === 0) {
          this.wrongOrders.add(i + 1)
        }
      }
    }

    // 3. 提取 sheet.answers / answers 列表 (支持 item.state === -1 / status === -1)
    const answers = Array.isArray(sheetData.answers) ? sheetData.answers : sheetData.sheet?.answers
    if (Array.isArray(answers)) {
      answers.forEach((a: any, idx: number) => {
        if (!a) return
        const aid = Number(a.questionId || a.id)
        const aKey = String(a.key || a.globalId || '')
        const isStateWrong =
          a.state === -1 ||
          String(a.state) === '-1' ||
          a.State === -1 ||
          String(a.State) === '-1' ||
          a.status === -1 ||
          String(a.status) === '-1' ||
          a.Status === -1 ||
          String(a.Status) === '-1'

        const isWrong =
          isStateWrong ||
          a.result === 2 ||
          a.result === -1 ||
          a.isWrong === true ||
          a.wrong === true ||
          a.correct === false ||
          a.score === 0 ||
          a.scoreRate === 0

        if (isWrong) {
          if (aid && !isNaN(aid)) this.wrongIds.add(aid)
          if (aKey) this.wrongKeys.add(aKey)
          this.wrongOrders.add(idx + 1)
        }
      })
    }

    // 4. 深度递归 card 结构 (支持 card.children 中每个题目的 state: -1 / State: -1)
    const cardObj = sheetData.card || sheetData.sheet?.card
    if (cardObj) {
      let cardOrder = 0
      const traverseCard = (node: any) => {
        if (!node) return
        if (Array.isArray(node)) {
          node.forEach(traverseCard)
          return
        }
        if (node.nodeType === 2 || node.key || node.id || node.userAnswer !== undefined || node.result !== undefined || node.state !== undefined || node.State !== undefined) {
          cardOrder++
          const numId = Number(node.id || node.questionId)
          const strKey = String(node.key || node.globalId || node.id || '')

          const isStateWrong =
            node.state === -1 ||
            String(node.state) === '-1' ||
            node.State === -1 ||
            String(node.State) === '-1' ||
            node.status === -1 ||
            String(node.status) === '-1' ||
            node.Status === -1 ||
            String(node.Status) === '-1'

          const isWrong =
            isStateWrong ||
            node.result === 2 ||
            node.result === -1 ||
            node.isWrong === true ||
            node.wrong === true ||
            node.correct === false ||
            (node.score === 0 && node.correctAnswer) ||
            (node.userAnswer && node.correctAnswer && String(node.userAnswer).trim().toUpperCase() !== String(node.correctAnswer).trim().toUpperCase())

          if (isWrong) {
            if (numId && !isNaN(numId)) this.wrongIds.add(numId)
            if (strKey) this.wrongKeys.add(strKey)
            this.wrongOrders.add(cardOrder)
          }
        }
        if (Array.isArray(node.children)) {
          node.children.forEach(traverseCard)
        }
      }
      traverseCard(cardObj)
    }

    // 同步到 window 全局变量供其他需要处读取
    if (typeof window !== 'undefined') {
      ;(window as any).__FENBI_MOCK_WRONG_IDS__ = Array.from(this.wrongIds)
      ;(window as any).__FENBI_MOCK_WRONG_KEYS__ = Array.from(this.wrongKeys)
      ;(window as any).__FENBI_MOCK_WRONG_ORDERS__ = Array.from(this.wrongOrders)
    }

    console.log('[粉笔适配器] 🎯 答题卡分析就绪:', {
      wrongOrders: Array.from(this.wrongOrders),
      wrongKeysCount: this.wrongKeys.size,
      wrongIdsCount: this.wrongIds.size,
      userAnswersCount: this.userAnswers.length,
    })
  }

  /**
   * 构建并输出合并打标后的 UnifiedPaper
   */
  public buildAggregatedPaper(settings: RenderTypographySettings = DEFAULT_TYPOGRAPHY_SETTINGS): UnifiedPaper | null {
    if (!this.staticPaper) return null

    // 组装并打入已知错题与作答
    const combinedData = {
      ...this.staticPaper,
      card: this.answerSheet?.card || this.staticPaper.card,
      sheet: this.answerSheet?.sheet || this.staticPaper.sheet,
      userAnswers: this.userAnswers.length > 0 ? this.userAnswers : this.staticPaper.userAnswers,
      userAnswersMap: this.userAnswersMap,
      wrongQuestionIds: Array.from(this.wrongIds),
      wrongQuestionKeys: Array.from(this.wrongKeys),
      wrongQuestionOrders: Array.from(this.wrongOrders),
      isMockExam: true,
    }

    let paper = adaptFenbiPaper(combinedData, settings)

    // 若网络层未能提取到错题，从当前 DOM 进行最后一次兜底扫描
    if (paper && (!paper.metadata?.totalWrong || paper.metadata.totalWrong === 0)) {
      const enriched = this.enrichFromDom(paper)
      if (enriched) paper = enriched
    }

    this.currentAggregatedPaper = paper
    return paper
  }

  /**
   * 兜底：从当前页面 DOM 答题卡识别红色错题序号
   */
  public enrichFromDom(paper: UnifiedPaper | null): UnifiedPaper | null {
    if (typeof document === 'undefined' || !paper || !paper.sections) return paper

    const wrongOrders = new Set<number>()
    try {
      const candidateNodes = Array.from(
        document.querySelectorAll(
          '.sheet-box [class*="item"], .answer-sheet [class*="item"], [class*="card"] [class*="item"], .fb-sheet span, .fb-sheet div, .fb-sheet li, [class*="sheet"] span, [class*="sheet"] div, [class*="sheet"] li, [class*="card"] span, [class*="card"] div, [class*="card"] li, .ant-badge, [class*="answer-card"]'
        )
      )

      for (const el of candidateNodes) {
        const txt = el.textContent?.trim()
        if (/^\d{1,3}$/.test(txt || '')) {
          const num = parseInt(txt!, 10)
          if (num >= 1 && num <= 200) {
            const cls = (el.className || '') + ' ' + ((el.parentElement as HTMLElement)?.className || '')
            const style = window.getComputedStyle(el)
            const color = style.color || ''
            const bg = style.backgroundColor || ''

            const isRedColor = (str: string) => {
              const m = str.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
              if (m) {
                const r = parseInt(m[1], 10)
                const g = parseInt(m[2], 10)
                const b = parseInt(m[3], 10)
                return r > 180 && g < 130 && b < 130
              }
              return false
            }

            const isRed =
              isRedColor(color) ||
              isRedColor(bg) ||
              color.includes('245, 34, 45') ||
              color.includes('255, 77, 79') ||
              color.includes('239, 68, 68') ||
              bg.includes('245, 34, 45') ||
              bg.includes('255, 77, 79') ||
              bg.includes('254, 226, 226')

            const isWrongCls = /wrong|error|incorrect|fail|danger|red/i.test(cls)
            if (isWrongCls || isRed) {
              wrongOrders.add(num)
              this.wrongOrders.add(num)
            }
          }
        }
      }
    } catch {}

    if (wrongOrders.size === 0) return paper

    console.log('[粉笔适配器] 🎯 从当前页面 DOM 答题卡捕获到错题题号:', Array.from(wrongOrders))

    let actualCount = 0
    for (const sec of paper.sections) {
      for (const q of sec.questions) {
        if (wrongOrders.has(q.order_num || 0)) {
          q.is_wrong = true
          actualCount++
        }
      }
    }

    if (paper.metadata) {
      paper.metadata.wrongQuestionOrders = Array.from(wrongOrders)
      paper.metadata.totalWrong = actualCount
    }
    return paper
  }
}

export const fenbiSession = new FenbiSessionManager()
