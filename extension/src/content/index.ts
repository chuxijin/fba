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
} from '../adapters'
import { mountReformatterApp, ReformatterAppInstance } from './ui/mount'

/**
 * 试卷排版 Content Script 核心枢纽 (遵循 KISS 极简架构)
 * 职责单一清晰：
 * 1. 挂载悬浮卡片与交互弹窗
 * 2. 接收网络嗅探与 SPA 路由消息，按平台分发至专属适配器
 * 3. 调度适配器流水线 (preparePaperForExport) 并分发排版交付
 */
;(function () {
  console.log('[公考内容排版] Content Script 启动')

  // 1. 注入主页面网络拦截器 Main World Script
  injectScript(chrome.runtime.getURL('injected.js'))

  // 2. 运行时核心状态
  let uiApp: ReformatterAppInstance | null = null
  let currentUnifiedPaper: UnifiedPaper | null = null
  let currentCapturedRaw: any = null
  let currentPaperPageUrl: string = ''
  let lastRouteUrl: string = location.href

  // 华图与事考帮临时中间状态
  let huatuLatestPractice: any = null

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
        if (lowerUrl.includes('/keypoint-tree')) {
          setCachedKeypointTree(data)
          return
        }

        const resolvedPaper = fenbiSession.handleNetworkPayload(url, data, DEFAULT_TYPOGRAPHY_SETTINGS)
        if (resolvedPaper && resolvedPaper.total_questions > 0) {
          console.log('[ContentScript] 🎉 粉笔会话聚合试卷:', resolvedPaper.title, `(${resolvedPaper.total_questions}题, 错题: ${resolvedPaper.metadata?.totalWrong || 0}题)`)
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
    console.log('[ContentScript] SPA 路由切换:', lastRouteUrl, '->', newUrl)
    lastRouteUrl = newUrl

    fenbiSession.reset()
    currentCapturedRaw = null
    currentUnifiedPaper = null
    currentPaperPageUrl = newUrl
    uiApp?.setPaperInfo('', 0)

    setTimeout(() => {
      resolveActivePaperLive(true).catch(() => {})
    }, 300)
  }

  // 6. 监听 Popup 弹窗指令
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
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
      console.warn('[ContentScript] 即时感知异常:', e)
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
      console.log(`[ContentScript] 正在聚合错题数据 (目标: ${targetLimit} 题)...`)
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
      console.warn('[ContentScript] 未过滤到具体错题，保留全卷')
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

  function injectScript(src: string) {
    const s = document.createElement('script')
    s.src = src
    s.onload = () => s.remove()
    ;(document.head || document.documentElement).appendChild(s)
  }
})()
