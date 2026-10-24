import {
  UnifiedPaper,
  DEFAULT_TYPOGRAPHY_SETTINGS,
  RenderTypographySettings,
  adaptFenbiPaper,
  adaptHuatuPaper,
  adaptShikaobangPaper,
  fetchFenbiPaperActively,
  fetchHuatuPaperActively,
  fetchShikaobangPaperActively,
  extractFenbiPaperFromDom,
  extractHuatuPaperFromDom,
  extractShikaobangPaperFromDom,
  fetchMistakeQuestionsByCount,
  parseMistakePageMeta,
  backfillPaperAnswers,
  setCachedKeypointTree,
  fenbiSession,
  buildWrongImportItems,
  IDLE_IMPORT_STATE,
  ImportState,
} from '../adapters'
import { mountReformatterApp, ReformatterAppInstance } from './ui/mount'
import { buildFenbiPracticeReport, fenbiReportRoute, readFenbiReportModules } from '../adapters/fenbi/report'
import type { FenbiHistoryItem, PracticeReportPayload } from '../adapters/fenbi/report'

/**
 * 试卷排版 Content Script 核心枢纽 (遵循 KISS 极简架构)
 * 职责单一清晰：
 * 1. 挂载悬浮卡片与交互弹窗
 * 2. 接收网络嗅探与 SPA 路由消息，按平台分发至专属适配器
 * 3. 调度适配器流水线 (preparePaperForExport) 并分发排版交付
 */
;(function () {

  // 1. 注入主页面网络拦截器 Main World Script
  injectScript(chrome.runtime.getURL('injected.js'))

  // 2. 运行时核心状态
  let uiApp: ReformatterAppInstance | null = null
  let currentUnifiedPaper: UnifiedPaper | null = null
  let currentCapturedRaw: any = null
  let currentPaperPageUrl: string = ''
  let lastRouteUrl: string = location.href
  let reportSolution: any = null
  const reportHistory = new Map<string, FenbiHistoryItem>()
  let reportPreparing = false
  let reportSaving = false

  // 华图与事考帮临时中间状态
  let huatuLatestPractice: any = null

  /**
   * 本页已成功导入过的错题键。
   * 后端对 (user_id, idempotency_key) 有唯一约束，重复提交会因幂等冲突失败，
   * 这里先做一层本地过滤，避免用户二次点击时看到一排无意义的失败。
   */
  const importedWrongKeys = new Set<string>()

  /** 最近一次成功导入的批次 ID，供「撤销本次导入」使用 */
  let lastImportBatchId = ''

  async function getReportHistory(href: string): Promise<FenbiHistoryItem | null> {
    const route = fenbiReportRoute(href)
    if (!route) return null
    if (reportHistory.has(route.key)) return reportHistory.get(route.key)!
    return new Promise(resolve => {
      const requestId = crypto.randomUUID()
      const finish = (item: FenbiHistoryItem|null) => {
        clearTimeout(timer)
        window.removeEventListener('message', listener)
        resolve(item)
      }
      const listener = (event: MessageEvent) => {
        if (event.source !== window || event.origin !== location.origin || event.data?.source !== 'GONGKAO_REPORT_HISTORY_RESULT'
          || event.data.requestId !== requestId || event.data.pageUrl !== href) return
        const item = event.data.item
        finish(item?.exerciseKey === route.key ? item : null)
      }
      const timer = setTimeout(() => finish(null), 22000)
      window.addEventListener('message', listener)
      window.postMessage({ source:'GONGKAO_REPORT_HISTORY_REQUEST', requestId }, location.origin)
    })
  }

  async function preparePracticeReport() {
    if (reportPreparing || reportSaving) return
    reportPreparing = true
    const href = location.href
    try {
      window.postMessage({ source:'GONGKAO_CONTENT_REQUEST_EXAM' }, location.origin)
      await new Promise(resolve => setTimeout(resolve, 100))
      if (location.href !== href) return
      const modules = readFenbiReportModules(document)
      // 先确认报告完整，再查询日期，避免在题目尚未就绪时遍历历史。
      const draft = buildFenbiPracticeReport(href, reportSolution, modules)
      const history = await getReportHistory(href)
      if (location.href !== href) return
      uiApp?.setReportDraft(buildFenbiPracticeReport(href, reportSolution, draft.modules, history))
    } catch (error:any) {
      if (location.href === href) uiApp?.setReportStatus('error', error?.message || '读取报告失败')
    } finally { reportPreparing = false }
  }

  async function savePracticeReport(draft: PracticeReportPayload) {
    if (reportSaving || draft.source_key !== fenbiReportRoute(location.href)?.key) return
    reportSaving = true
    const href = location.href
    uiApp?.setReportStatus('saving')
    try {
      const result = await chrome.runtime.sendMessage({ type:'IMPORT_PRACTICE_REPORT', payload:draft })
      if (!result?.success) throw new Error(result?.error || '导入失败')
      if (location.href === href) uiApp?.setReportStatus('done', result.created
        ? '导入成功，可在小程序「练习数据 → 导入/手动记录」查看三级明细和对比。'
        : '这份报告已导入，无需重复保存。可在小程序「练习数据」中查看或编辑。')
    } catch (error:any) {
      if (location.href === href) uiApp?.setReportStatus('error', error?.message || '导入失败，请重试')
    } finally { reportSaving = false }
  }

  // 3. 挂载 Vue 悬浮卡片与交互弹窗
  function initUi() {
    try {
      uiApp = mountReformatterApp({
        onRequestReformat: async () => {
          uiApp?.openModal()
          window.postMessage({ source: 'GONGKAO_CONTENT_REQUEST_EXAM' }, '*')
          if (currentUnifiedPaper && currentUnifiedPaper.total_questions > 0) {
            currentUnifiedPaper = fenbiSession.enrichFromDom(currentUnifiedPaper)
            if (currentUnifiedPaper) uiApp?.setPaper(currentUnifiedPaper)
          } else {
            await resolveActivePaperLive(true)
          }
        },
        onRequestQuickPrint: () => handleExport(DEFAULT_TYPOGRAPHY_SETTINGS, 'mobile_sync'),
        onDoExport: (settings: RenderTypographySettings, target: 'computer_download' | 'mobile_sync') =>
          handleExport(settings, target),
        onImportWrong: () => handleImportWrongQuestions(),
        onUndoImport: () => handleUndoImportBatch(),
        onImportReport: () => preparePracticeReport(),
        onSaveReport: (draft) => savePracticeReport(draft),
      })

      // 挂载后立即同步试卷状态给悬浮卡片
      const cached = currentUnifiedPaper || fenbiSession.getPaper()
      if (cached && cached.total_questions > 0) {
        currentUnifiedPaper = cached
        currentPaperPageUrl = location.href
        uiApp?.setPaper(currentUnifiedPaper)
      }
    } catch (e) {
      console.warn('[ContentScript] 挂载 UI 异常:', e)
    }
  }

  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    initUi()
  } else {
    window.addEventListener('load', initUi)
  }

  // 4. 监听来自 injected.js 的透明网络拦截与 SPA 路由消息
  window.addEventListener('message', (event) => {
    if (event.source !== window || event.origin !== location.origin) return
    if (event.data?.source !== 'GONGKAO_REFORMATTER_INTERCEPTOR') return

    if (event.data?.type === 'SPA_ROUTE_CHANGED') {
      handleRouteUrlChange(event.data.url)
      return
    }

    if (event.data?.type === 'RAW_API_INTERCEPTED') {
      const { url, data } = event.data
      if (!data) return
      const lowerUrl = (url || '').toLowerCase()

      // ==========================================
      // 分支 A: 粉笔题库生态 (由 fenbiSession 统一聚合闭环)
      // ==========================================
      const isFenbi =
        lowerUrl.includes('fenbi.com') ||
        lowerUrl.includes('fbstatic.cn') ||
        lowerUrl.includes('fenbike.cn') ||
        location.href.includes('fenbi.com')

      if (isFenbi) {
        const payload = data?.data || data
        if (lowerUrl.includes('/combine/exercise/getsolution') && payload?.exerciseId === fenbiReportRoute(location.href)?.key)
          reportSolution = payload
        if (lowerUrl.includes('/getexercisebriefhistory')) {
          for (const item of payload?.historyItems || []) {
            if (item.exerciseKey) reportHistory.set(item.exerciseKey, {
              exerciseKey:item.exerciseKey, updatedTime:item.updatedTime, score:item.score, fullScore:item.fullScore,
            })
          }
        }
        if (lowerUrl.includes('/keypoint-tree')) {
          setCachedKeypointTree(data)
          return
        }

        const resolvedPaper = fenbiSession.handleNetworkPayload(url, data, DEFAULT_TYPOGRAPHY_SETTINGS)
        if (resolvedPaper && resolvedPaper.total_questions > 0) {
          currentUnifiedPaper = resolvedPaper
          currentPaperPageUrl = location.href
          uiApp?.setPaper(currentUnifiedPaper)
        }
        return
      }

      // ==========================================
      // 分支 B: 华图在线生态
      // ==========================================
      const isHuatu = lowerUrl.includes('huatu.com') || location.href.includes('huatu.com')
      if (isHuatu) {
        if (lowerUrl.includes('/practices/')) {
          huatuLatestPractice = data?.data || data
          return
        }
        if (lowerUrl.includes('/questions')) {
          const qData = data?.data || data
          const singleList = qData?.singleQuestions || []
          const compList = qData?.compositeQuestions || []
          if (Array.isArray(singleList) && singleList.length > 0) {
            const practice = huatuLatestPractice || {}
            const title = practice.name || practice.paper?.name || '华图在线行测练习'
            currentUnifiedPaper = adaptHuatuPaper(
              {
                platform: 'huatu',
                title,
                name: title,
                singleQuestions: singleList,
                compositeQuestions: compList,
                modules: practice.paper?.modules || practice.modules || [],
                practice,
                total: singleList.length,
              },
              DEFAULT_TYPOGRAPHY_SETTINGS
            )
            currentPaperPageUrl = location.href
            uiApp?.setPaper(currentUnifiedPaper)
          }
          return
        }
      }

      // ==========================================
      // 分支 C: 事考帮生态
      // ==========================================
      const isShikaobang = lowerUrl.includes('shikaobang.cn') || location.href.includes('shikaobang.cn')
      if (isShikaobang) {
        if (lowerUrl.includes('/practiceexam/getpapercontent') || lowerUrl.includes('/exercise/get-question')) {
          const pData = data?.data || data
          currentUnifiedPaper = adaptShikaobangPaper(
            {
              platform: 'shikaobang',
              name: pData?.paper?.name || pData?.title || '事业单位全真模拟考试',
              ...pData,
            },
            DEFAULT_TYPOGRAPHY_SETTINGS
          )
          currentPaperPageUrl = location.href
          uiApp?.setPaper(currentUnifiedPaper)
          return
        }
      }
    }
  })

  // 5. 监听 SPA 前端路由与轻量巡检
  window.addEventListener('popstate', () => handleRouteUrlChange(location.href))
  window.addEventListener('hashchange', () => handleRouteUrlChange(location.href))

  setInterval(() => {
    if (location.href !== lastRouteUrl) {
      handleRouteUrlChange(location.href)
    }
  }, 800)

  function handleRouteUrlChange(newUrl: string) {
    if (newUrl === lastRouteUrl && currentPaperPageUrl === newUrl) return
    lastRouteUrl = newUrl

    fenbiSession.reset()
    reportSolution = null
    currentCapturedRaw = null
    currentUnifiedPaper = null
    currentPaperPageUrl = newUrl
    importedWrongKeys.clear()
    uiApp?.resetPaper()

    setTimeout(() => {
      resolveActivePaperLive(true).catch(() => {})
    }, 300)
  }

  // 6. 监听 Popup 弹窗指令
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    // 后台分片导入的进度回传
    if (msg.type === 'IMPORT_PROGRESS') {
      const payload = msg.payload || {}
      uiApp?.setImportState({
        status: 'running',
        done: Number(payload.done || 0),
        total: Number(payload.total || 0),
        imported: Number(payload.imported || 0),
        failed: Number(payload.failed || 0),
        skipped: 0,
      })
      sendResponse({ success: true })
      return true
    }
    if (msg.type === 'CHECK_STATUS') {
      const activePaper = currentUnifiedPaper || fenbiSession.getPaper()
      if (activePaper && activePaper.total_questions > 0) {
        currentUnifiedPaper = activePaper
        uiApp?.setPaper(activePaper)
        sendResponse({
          success: true,
          hasContent: true,
          paperTitle: activePaper.title || '',
          questionCount: activePaper.total_questions || 0,
        })
        return true
      }

      resolveActivePaperLive(false).then((ready) => {
        const paper = currentUnifiedPaper || fenbiSession.getPaper()
        const hasContent = Boolean(ready && paper && paper.total_questions > 0)
        if (paper && hasContent) uiApp?.setPaper(paper)
        sendResponse({
          success: true,
          hasContent,
          paperTitle: paper?.title || '',
          questionCount: paper?.total_questions || 0,
        })
      })
      return true
    }
    if (msg.type === 'START_REFORMAT') {
      resolveActivePaperLive(false).then((ready) => {
        if (ready && currentUnifiedPaper) uiApp?.openModal()
      })
      sendResponse({ success: true })
      return true
    }
    if (msg.type === 'QUICK_PRINT') {
      resolveActivePaperLive(false).then((ready) => {
        if (ready && currentUnifiedPaper) {
          handleExport(DEFAULT_TYPOGRAPHY_SETTINGS, 'mobile_sync')
        }
      })
      sendResponse({ success: true })
      return true
    }
  })

  /**
   * 全场景即时感知流水线 (按需即时分析当前页面)
   */
  async function resolveActivePaperLive(forceRefresh: boolean = false): Promise<boolean> {
    const currentUrl = location.href

    // 向主页面 MAIN 世界请求重派发已捕获的网络数据包
    window.postMessage({ source: 'GONGKAO_CONTENT_REQUEST_EXAM' }, '*')

    // 优先层 0: 粉笔会话聚合引擎中的有效试卷
    const sessionPaper = fenbiSession.getPaper()
    if (!forceRefresh && sessionPaper && sessionPaper.total_questions > 0) {
      currentUnifiedPaper = sessionPaper
      currentPaperPageUrl = currentUrl
      uiApp?.setPaper(currentUnifiedPaper)
      return true
    }

    if (!forceRefresh && currentUnifiedPaper && currentPaperPageUrl === currentUrl && currentUnifiedPaper.total_questions > 0) {
      uiApp?.setPaper(currentUnifiedPaper)
      return true
    }

    // 优先层 1: 内存最新网络包
    if (currentCapturedRaw && currentPaperPageUrl === currentUrl) {
      if (currentCapturedRaw.platform === 'shikaobang' || currentUrl.includes('shikaobang.cn')) {
        currentUnifiedPaper = adaptShikaobangPaper(currentCapturedRaw, DEFAULT_TYPOGRAPHY_SETTINGS)
      } else if (currentCapturedRaw.platform === 'huatu' || currentUrl.includes('huatu.com')) {
        currentUnifiedPaper = adaptHuatuPaper(currentCapturedRaw, DEFAULT_TYPOGRAPHY_SETTINGS)
      } else {
        currentUnifiedPaper = adaptFenbiPaper(currentCapturedRaw, DEFAULT_TYPOGRAPHY_SETTINGS)
      }
      if (currentUnifiedPaper && currentUnifiedPaper.total_questions > 0) {
        uiApp?.setPaper(currentUnifiedPaper)
        return true
      }
    }

    try {
      if (currentUrl.includes('shikaobang.cn')) {
        const activePaper = await fetchShikaobangPaperActively(DEFAULT_TYPOGRAPHY_SETTINGS)
        const domPaper = !activePaper || activePaper.total_questions === 0 ? extractShikaobangPaperFromDom(DEFAULT_TYPOGRAPHY_SETTINGS) : null
        currentUnifiedPaper = activePaper && activePaper.total_questions > 0 ? activePaper : domPaper
      } else if (currentUrl.includes('huatu.com')) {
        const activePaper = await fetchHuatuPaperActively(DEFAULT_TYPOGRAPHY_SETTINGS)
        const domPaper = !activePaper || activePaper.total_questions === 0 ? extractHuatuPaperFromDom(DEFAULT_TYPOGRAPHY_SETTINGS) : null
        currentUnifiedPaper = activePaper && activePaper.total_questions > 0 ? activePaper : domPaper
      } else {
        const activePaper = await fetchFenbiPaperActively(DEFAULT_TYPOGRAPHY_SETTINGS)
        const domPaper = !activePaper || activePaper.total_questions === 0 ? extractFenbiPaperFromDom(DEFAULT_TYPOGRAPHY_SETTINGS) : null
        currentUnifiedPaper = activePaper && activePaper.total_questions > 0 ? activePaper : domPaper
      }

      if (currentUnifiedPaper && currentUnifiedPaper.total_questions > 0) {
        currentPaperPageUrl = currentUrl
        currentUnifiedPaper = fenbiSession.enrichFromDom(currentUnifiedPaper)
        if (currentUnifiedPaper) uiApp?.setPaper(currentUnifiedPaper)
        return true
      }
    } catch (e: any) {
    }

    return false
  }

  setTimeout(() => {
    resolveActivePaperLive(false).catch(() => {})
  }, 500)
  setTimeout(() => {
    if (!currentUnifiedPaper || currentUnifiedPaper.total_questions === 0) {
      resolveActivePaperLive(true).catch(() => {})
    }
  }, 1500)

  /**
   * 极简高内聚：统一准备用于排版导出的标准化试卷对象
   */
  async function preparePaperForExport(settings: RenderTypographySettings): Promise<UnifiedPaper | null> {
    const currentUrl = location.href
    const isMistake = currentUrl.includes('/error') || currentUrl.includes('/errors/')
    const mistakeMeta = parseMistakePageMeta(currentUrl)

    // 1. 错题场景：内聚错题聚合引擎（自动完成多源ID、跨页嗅探与全量要素补全）
    if (isMistake || mistakeMeta) {
      const targetLimit = settings.questionLimit || 10
      const fetchedMistakePaper = await fetchMistakeQuestionsByCount({
        keypointId: mistakeMeta?.keypointId,
        keypointName: mistakeMeta?.keypointName,
        targetCount: targetLimit,
        settings,
      })
      if (fetchedMistakePaper && fetchedMistakePaper.total_questions > 0) {
        return fetchedMistakePaper
      }
    }

    // 2. 模考/真题网络数据包场景
    if (currentCapturedRaw && currentPaperPageUrl === currentUrl) {
      let rawAdapted: UnifiedPaper
      if (currentCapturedRaw.platform === 'shikaobang' || currentUrl.includes('shikaobang.cn')) {
        rawAdapted = adaptShikaobangPaper(currentCapturedRaw, settings)
      } else if (currentCapturedRaw.platform === 'huatu' || currentUrl.includes('huatu.com')) {
        rawAdapted = adaptHuatuPaper(currentCapturedRaw, settings)
      } else {
        rawAdapted = adaptFenbiPaper(currentCapturedRaw, settings)
      }

      if (rawAdapted && rawAdapted.total_questions > 0) {
        if (settings.exportScope === 'mistake_only') {
          rawAdapted = filterOnlyMistakeQuestions(rawAdapted)
        }
        return settings.includeAnswer ? await backfillPaperAnswers(rawAdapted) : rawAdapted
      }
    }

    // 3. 通用感知与屏幕 DOM 兜底场景
    const ready = await resolveActivePaperLive(false)
    if (ready && currentUnifiedPaper && currentUnifiedPaper.total_questions > 0) {
      let paper = currentUnifiedPaper
      if (settings.exportScope === 'mistake_only') {
        paper = filterOnlyMistakeQuestions(paper)
      }
      if (settings.includeAnswer) {
        try {
          paper = await backfillPaperAnswers(paper)
        } catch {}
      }
      return paper
    }

    return null
  }

  /**
   * 模考专属：过滤并重新编排考生的错题试卷
   */
  function filterOnlyMistakeQuestions(paper: UnifiedPaper): UnifiedPaper {
    const wrongIds = new Set<number>((paper.metadata?.wrongQuestionIds || []).map(Number))
    const wrongKeys = new Set<string>((paper.metadata?.wrongQuestionKeys || []).map(String))
    const wrongOrders = new Set<number>((paper.metadata?.wrongQuestionOrders || []).map(Number))
    const newSections: any[] = []
    let newOrder = 1

    for (const sec of paper.sections) {
      const wrongQs: any[] = []
      for (const q of sec.questions) {
        const qid = Number(q.question_id || q.id)
        const qKey = String((q as any).key || (q as any).globalId || q.id || '')
        const isWrong =
          q.is_wrong === true ||
          (qid && !isNaN(qid) && wrongIds.has(qid)) ||
          (qKey && wrongKeys.has(qKey)) ||
          (q.order_num && wrongOrders.has(q.order_num))
        if (isWrong) {
          wrongQs.push({
            ...q,
            order_num: newOrder++,
            source: q.source ? `${q.source} (模考原第${q.order_num || ''}题)` : `模考原第${q.order_num || ''}题`,
          })
        }
      }
      if (wrongQs.length > 0) {
        newSections.push({
          name: sec.name,
          description: sec.description,
          questions: wrongQs,
        })
      }
    }

    // 兜底：若经过过滤未匹配到错题（例如全对或无作答对错标记），保留原试卷
    if (newSections.length === 0) {
      return paper
    }

    const totalWrong = newSections.reduce((sum, s) => sum + s.questions.length, 0)
    return {
      ...paper,
      title: paper.title.includes('错题') ? paper.title : `${paper.title}（模考错题订正版）`,
      total_questions: totalWrong,
      sections: newSections,
      metadata: {
        ...paper.metadata,
        isMistakeOnly: true,
        originalTotal: paper.total_questions,
      },
    }
  }

  
  async function handleExport(settings: RenderTypographySettings, target: 'computer_download' | 'mobile_sync') {
    uiApp?.showLoading(target)

    try {
      const paperToSend = await preparePaperForExport(settings)
      if (!paperToSend || paperToSend.total_questions === 0) {
        uiApp?.showError('未能从当前页面捕获到有效题目。请确认页面中的题目已完整显示，或按 F5 刷新后重试！')
        return
      }

      if (!chrome.runtime?.id) {
        uiApp?.showError('检测到插件刚刚更新，请按 F5 刷新网页后重试！')
        return
      }

      chrome.runtime.sendMessage(
        {
          type: 'RENDER_AND_EXPORT',
          payload: {
            paper: paperToSend,
            settings,
            target,
          },
        },
        (response) => {
          if (chrome.runtime.lastError) {
            uiApp?.showError('通信异常，请按 F5 刷新页面后重试')
            return
          }

          if (!response || !response.success) {
            uiApp?.showError(response?.error || '后端排版渲染失败，请检查服务状态')
            return
          }

          uiApp?.showDelivery({
            qrCodeUrl: response.qrCodeUrl,
            savedPath: response.savedPath,
            remainingQuota: response.remainingQuota !== undefined ? response.remainingQuota : undefined,
          })
        }
      )
    } catch (err: any) {
      if (err?.message?.includes('Extension context invalidated')) {
        uiApp?.showError('检测到插件刚刚更新，请按 F5 刷新当前网页后重试！')
      } else {
        uiApp?.showError(err?.message || '导出异常，请稍后重试')
      }
    }
  }

  /**
   * 把当前页面的错题导入到后端「错题待复盘」队列。
   *
   * 数据来源：当前页已捕获的 UnifiedPaper 中 is_wrong === true 的题目。
   * 答案只从已拦截到的解析数据里补齐（backfillPaperAnswers 纯内存，不发起外发请求），
   * 没有答案的题目在后端必填校验下无法成立，按跳过处理。
   */
  async function handleImportWrongQuestions() {
    const setState = (state: ImportState) => uiApp?.setImportState(state)

    try {
      if (!currentUnifiedPaper || currentUnifiedPaper.total_questions === 0) {
        await resolveActivePaperLive(true).catch(() => {})
      }

      const activePaper = currentUnifiedPaper
      if (!activePaper || activePaper.total_questions === 0) {
        setState({ ...IDLE_IMPORT_STATE, status: 'error', message: '未捕获到当前页面题目，请按 F5 刷新后重试' })
        return
      }

      let paper: UnifiedPaper = activePaper
      try {
        paper = await backfillPaperAnswers(paper)
      } catch {}

      const built = buildWrongImportItems(paper)
      // 过滤掉本页已经成功导入过的题（后端幂等键重复会报错，这里提前挡掉）
      const items = built.items.filter((item) => !importedWrongKeys.has(item.external_key))
      const alreadyImported = built.items.length - items.length
      const skipped = built.skipped

      if (items.length === 0) {
        setState({
          ...IDLE_IMPORT_STATE,
          status: alreadyImported > 0 ? 'done' : 'error',
          total: built.items.length,
          imported: alreadyImported,
          skipped: skipped.length,
          message:
            alreadyImported > 0
              ? '本页错题已全部导入过，可到小程序查看'
              : skipped.length > 0
                ? `没有可导入的错题：${skipped.length} 道缺少答案或题干`
                : '当前页面没有检测到错题',
        })
        return
      }

      setState({ ...IDLE_IMPORT_STATE, status: 'running', total: items.length, skipped: skipped.length })

      if (!chrome.runtime?.id) {
        setState({ ...IDLE_IMPORT_STATE, status: 'error', message: '检测到插件刚刚更新，请按 F5 刷新页面后重试' })
        return
      }

      chrome.runtime.sendMessage(
        { type: 'IMPORT_WRONG_QUESTIONS', payload: { items, paperTitle: paper.title } },
        (response) => {
          if (chrome.runtime.lastError) {
            setState({ ...IDLE_IMPORT_STATE, status: 'error', message: '通信异常，请按 F5 刷新页面后重试' })
            return
          }
          if (!response || !response.success) {
            setState({
              ...IDLE_IMPORT_STATE,
              status: 'error',
              total: items.length,
              skipped: skipped.length,
              message: response?.error || '导入失败，请稍后重试',
            })
            return
          }

          const imported = Number(Math.max(Number(response.imported || 0), alreadyImported))
          const failed = Number(response.failed || 0)
          if (typeof response.importBatchId === 'string' && response.importBatchId) {
            lastImportBatchId = response.importBatchId
          }
          if (Array.isArray(response.importedKeys)) {
            for (const key of response.importedKeys) {
              if (typeof key === 'string' && key) importedWrongKeys.add(key)
            }
          }
          // 整批都是「已导入过」：把键记下来，避免同页反复点击重复请求
          if (Array.isArray(response.duplicateKeys)) {
            for (const key of response.duplicateKeys) {
              if (typeof key === 'string' && key) importedWrongKeys.add(key)
            }
          }

          if (response.allDuplicates) {
            setState({
              status: 'done',
              done: items.length,
              total: items.length,
              imported: 0,
              failed: 0,
              skipped: skipped.length + alreadyImported,
              message: '本页错题之前已导入过，可到小程序「待复盘错题」查看',
            })
            return
          }

          setState({
            status: failed > 0 && imported === 0 ? 'error' : 'done',
            done: items.length,
            total: items.length,
            imported,
            failed,
            skipped: skipped.length + alreadyImported,
            message: response.error || undefined,
            batchId: typeof response.importBatchId === 'string' ? response.importBatchId : undefined,
          })
        }
      )
    } catch (err: any) {
      if (err?.message?.includes('Extension context invalidated')) {
        setState({ ...IDLE_IMPORT_STATE, status: 'error', message: '检测到插件刚刚更新，请按 F5 刷新页面后重试' })
      } else {
        setState({ ...IDLE_IMPORT_STATE, status: 'error', message: err?.message || '导入异常，请稍后重试' })
      }
    }
  }

  /**
   * 撤销上一次导入（按批次整批软删）
   */
  async function handleUndoImportBatch() {
    const batchId = lastImportBatchId
    if (!batchId) {
      uiApp?.setImportState({ ...IDLE_IMPORT_STATE, status: 'error', message: '没有可撤销的导入批次' })
      return
    }

    uiApp?.setImportState({
      ...IDLE_IMPORT_STATE,
      status: 'running',
      total: 1,
      message: '正在撤销本次导入…',
    })

    chrome.runtime.sendMessage({ type: 'UNDO_IMPORT_BATCH', payload: { importBatchId: batchId } }, (response) => {
      if (chrome.runtime.lastError || !response || !response.success) {
        uiApp?.setImportState({
          ...IDLE_IMPORT_STATE,
          status: 'error',
          message: response?.error || '撤销失败，请稍后重试',
        })
        return
      }
      lastImportBatchId = ''
      importedWrongKeys.clear()
      uiApp?.setImportState({
        ...IDLE_IMPORT_STATE,
        status: 'done',
        imported: 0,
        message: `已撤销 ${Number(response.deletedStates || 0)} 道错题`,
      })
    })
  }

  function injectScript(src: string) {
    const s = document.createElement('script')
    s.src = src
    s.onload = () => s.remove()
    ;(document.head || document.documentElement).appendChild(s)
  }
})()
