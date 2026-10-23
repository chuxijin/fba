import {
  saveAuthSession,
  logoutAuthSession,
  fetchScanQrcode,
  pollScanStatus,
  mockConfirmScan,
  fetchCaptcha,
  loginWithPassword,
  sendAuthMessage,
  CaptchaResult,
} from '../utils/auth'
import { accountStore, AccountState } from '../utils/account-state'
import { BACKEND_BASE, LOCAL_SITE_ORIGINS, type QuotaInfo, type TokenInfo, type UserInfo } from '../utils/auth-protocol'

document.addEventListener('DOMContentLoaded', async () => {
  // ── 视图容器 ──
  const viewMain   = document.getElementById('view-main')!
  const viewScan   = document.getElementById('view-scan')!
  const accountBar = document.getElementById('account-bar')!
  const footerNav  = document.getElementById('footer-nav')!
  const diagnostics = document.getElementById('auth-diagnostics') as HTMLDetailsElement
  const diagnosticReport = document.getElementById('auth-diagnostics-report')!
  const btnDiagnose = document.getElementById('btn-auth-diagnose') as HTMLButtonElement
  const btnCopyReport = document.getElementById('btn-auth-copy') as HTMLButtonElement
  const btnReconnect = document.getElementById('btn-auth-reconnect') as HTMLButtonElement

  async function diagnoseAuth() {
    if (btnDiagnose.disabled) return
    btnDiagnose.disabled = true
    btnCopyReport.disabled = true
    btnCopyReport.textContent = '复制检查结果'
    diagnosticReport.textContent = '正在检查登录同步…'
    try {
      const response = await sendAuthMessage<{ report: string }>({ type: 'GET_AUTH_DIAGNOSTICS' }, '检查超时，请重新加载扩展后重试', 12000)
      if (typeof response.report !== 'string') throw new Error('登录同步检查响应无效')
      diagnosticReport.textContent = response.report
    } catch (error) {
      diagnosticReport.textContent = error instanceof Error ? error.message : '检查失败，请重试'
    } finally {
      btnDiagnose.disabled = false
      btnCopyReport.disabled = false
    }
  }
  diagnostics.addEventListener('toggle', () => { if (diagnostics.open) void diagnoseAuth() })
  btnDiagnose.addEventListener('click', () => { void diagnoseAuth() })
  btnReconnect.addEventListener('click', async () => {
    btnReconnect.disabled = true
    btnDiagnose.disabled = true
    btnCopyReport.disabled = true
    diagnosticReport.textContent = '正在重新连接已打开的官网并验证登录…'
    try {
      const response = await sendAuthMessage<{ data: QuotaInfo }>({ type: 'RECONNECT_SITE_AUTH' }, '同步超时，请检查后端连接后重试')
      if (!response.data?.is_logged_in) throw new Error('未读取到有效登录。请保持已登录的本地官网打开，再检查下方连接状态。')
      await syncAuth()
      btnDiagnose.disabled = false
      await diagnoseAuth()
    } catch (error) {
      diagnosticReport.textContent = error instanceof Error ? error.message : '同步失败，请重试'
    } finally {
      btnReconnect.disabled = false
      btnDiagnose.disabled = false
      btnCopyReport.disabled = false
    }
  })
  btnCopyReport.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(diagnosticReport.textContent || '')
      btnCopyReport.textContent = '已复制'
    } catch { btnCopyReport.textContent = '请选中上方文字复制' }
  })

  // ── 主视图 DOM ──
  const heroCard        = document.getElementById('hero-card')!
  const heroEmpty       = document.getElementById('hero-empty')!
  const heroEmptyTitle  = document.getElementById('hero-empty-title-text')!
  const heroEmptyDesc   = document.getElementById('hero-empty-desc')!
  const heroReady       = document.getElementById('hero-ready')!
  const readyPaperTitle = document.getElementById('ready-paper-title')!
  const readyPaperMeta  = document.getElementById('ready-paper-meta')!
  const btnReformat     = document.getElementById('btn-reformat')!

  // ── 账户底栏 DOM ──
  const acctGuest     = document.getElementById('acct-guest')!
  const acctUser      = document.getElementById('acct-user')!
  const acctStatusTitle = document.getElementById('acct-status-title')!
  const acctStatusDesc = document.getElementById('acct-status-desc')!
  const btnAuthRetry = document.getElementById('btn-auth-retry')!
  const btnQuotaRetry = document.getElementById('btn-quota-retry')!
  const acctQuotaLabel = document.getElementById('acct-quota-label')!
  const acctQuotaSuffix = document.getElementById('acct-quota-suffix')!
  const guestQuotaSub = document.getElementById('guest-quota-sub')!
  const btnShowScan   = document.getElementById('btn-show-scan')!
  const acctAvatarImg     = document.getElementById('acct-avatar-img') as HTMLImageElement
  const acctAvatarFallback= document.getElementById('acct-avatar-fallback')!
  const acctUserName   = document.getElementById('acct-user-name')!
  const acctQuotaNum   = document.getElementById('acct-quota-num')!
  const btnLogout      = document.getElementById('btn-logout')!

  // ── 登录视图共用 DOM ──
  const btnBack        = document.getElementById('btn-back')!
  const scanHeaderTitle = document.getElementById('scan-header-title')!
  const tabScan        = document.getElementById('tab-scan')!
  const tabPwd         = document.getElementById('tab-pwd')!
  const panelScan      = document.getElementById('panel-scan')!
  const panelPwd       = document.getElementById('panel-pwd')!

  // ── 扫码面板 DOM ──
  const scanQrImg      = document.getElementById('scan-qr-img') as HTMLImageElement
  const scanQrLoading  = document.getElementById('scan-qr-loading')!
  const scanMainHint   = document.getElementById('scan-main-hint')!
  const btnScanMock    = document.getElementById('btn-scan-mock')!

  // ── 账号密码表单 DOM ──
  const pwdUsername     = document.getElementById('pwd-username') as HTMLInputElement
  const pwdPassword     = document.getElementById('pwd-password') as HTMLInputElement
  const btnTogglePwd    = document.getElementById('btn-toggle-pwd')!
  const pwdCaptchaGroup = document.getElementById('pwd-captcha-group')!
  const pwdCaptcha      = document.getElementById('pwd-captcha') as HTMLInputElement
  const captchaImgWrap  = document.getElementById('captcha-img-wrap')!
  const pwdCaptchaImg   = document.getElementById('pwd-captcha-img') as HTMLImageElement
  const captchaLoading  = document.getElementById('captcha-loading')!
  const pwdErrorMsg     = document.getElementById('pwd-error-msg')!
  const btnPwdLogin     = document.getElementById('btn-pwd-login') as HTMLButtonElement
  const pwdLoginText    = document.getElementById('pwd-login-text')!
  const btnDevFill      = document.getElementById('btn-dev-fill')!

  let currentSceneId = ''
  let pollTimer: ReturnType<typeof setTimeout> | null = null
  let scanGeneration = 0
  let currentCaptcha: CaptchaResult | null = null

  // ── 视图切换 ──
  function showMainView() {
    viewMain.style.display   = 'flex'
    accountBar.style.display = 'flex'
    footerNav.style.display  = 'flex'
    diagnostics.style.display = 'block'
    viewScan.style.display   = 'none'
    stopPolling()
  }

  function showScanView() {
    viewMain.style.display   = 'none'
    accountBar.style.display = 'none'
    footerNav.style.display  = 'none'
    diagnostics.style.display = 'none'
    viewScan.style.display   = 'flex'
  }

  // ── 登录 Tab 切换 ──
  function switchLoginTab(tab: 'scan' | 'pwd') {
    if (tab === 'scan') {
      tabScan.classList.add('active')
      tabPwd.classList.remove('active')
      panelScan.style.display = 'flex'
      panelPwd.style.display = 'none'
      if (scanHeaderTitle) scanHeaderTitle.textContent = '微信扫一扫授权登录'
      void startScanLogin()
    } else {
      tabScan.classList.remove('active')
      tabPwd.classList.add('active')
      panelScan.style.display = 'none'
      panelPwd.style.display = 'flex'
      if (scanHeaderTitle) scanHeaderTitle.textContent = '账号密码登录'
      stopPolling()
      loadCaptcha()
      setTimeout(() => pwdUsername.focus(), 50)
    }
  }

  tabScan.addEventListener('click', () => switchLoginTab('scan'))
  tabPwd.addEventListener('click', () => switchLoginTab('pwd'))

  // ── 图形验证码拉取与刷新 ──
  async function loadCaptcha() {
    if (!captchaLoading || !pwdCaptchaImg) return
    captchaLoading.style.display = 'inline'
    pwdCaptchaImg.style.display = 'none'
    try {
      currentCaptcha = await fetchCaptcha(BACKEND_BASE)
      if (currentCaptcha.is_enabled && currentCaptcha.image) {
        pwdCaptchaGroup.style.display = 'flex'
        pwdCaptchaImg.src = currentCaptcha.image
        pwdCaptchaImg.style.display = 'block'
      } else {
        pwdCaptchaGroup.style.display = 'none'
      }
    } catch {
      pwdCaptchaGroup.style.display = 'none'
    } finally {
      captchaLoading.style.display = 'none'
    }
  }

  if (captchaImgWrap) {
    captchaImgWrap.addEventListener('click', () => {
      loadCaptcha()
      if (pwdCaptcha) pwdCaptcha.value = ''
    })
  }

  // 密码显示/隐藏切换
  if (btnTogglePwd) {
    btnTogglePwd.addEventListener('click', () => {
      if (pwdPassword.type === 'password') {
        pwdPassword.type = 'text'
        btnTogglePwd.textContent = '🙈'
      } else {
        pwdPassword.type = 'password'
        btnTogglePwd.textContent = '👁️'
      }
    })
  }

  // 账号密码登录处理
  function showPwdError(msg: string) {
    if (pwdErrorMsg) {
      pwdErrorMsg.textContent = msg
      pwdErrorMsg.style.display = 'flex'
    }
  }

  async function handlePasswordLogin() {
    const username = pwdUsername.value.trim()
    const password = pwdPassword.value
    const captchaVal = pwdCaptcha ? pwdCaptcha.value.trim() : ''

    if (pwdErrorMsg) {
      pwdErrorMsg.style.display = 'none'
      pwdErrorMsg.textContent = ''
    }

    if (!username) {
      showPwdError('请输入用户名或手机号')
      pwdUsername.focus()
      return
    }
    if (!password) {
      showPwdError('请输入登录密码')
      pwdPassword.focus()
      return
    }
    if (currentCaptcha?.is_enabled && !captchaVal) {
      showPwdError('请输入图形验证码')
      if (pwdCaptcha) pwdCaptcha.focus()
      return
    }

    btnPwdLogin.disabled = true
    if (pwdLoginText) pwdLoginText.textContent = '登录中…'

    try {
      const res = await loginWithPassword(
        {
          username,
          password,
          uuid: currentCaptcha?.uuid,
          captcha: captchaVal || undefined,
        },
        BACKEND_BASE
      )

      await completeLogin(res.token, res.user)
    } catch (err: any) {
      showPwdError(err?.message || '登录失败，请检查账号密码')
      if (currentCaptcha?.is_enabled) {
        loadCaptcha()
        if (pwdCaptcha) pwdCaptcha.value = ''
      }
    } finally {
      btnPwdLogin.disabled = false
      if (pwdLoginText) pwdLoginText.textContent = '立即登录'
    }
  }

  if (btnPwdLogin) {
    btnPwdLogin.addEventListener('click', handlePasswordLogin)
  }

  if (pwdUsername) {
    pwdUsername.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') pwdPassword.focus()
    })
  }
  if (pwdPassword) {
    pwdPassword.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        if (currentCaptcha?.is_enabled) {
          pwdCaptcha.focus()
        } else {
          handlePasswordLogin()
        }
      }
    })
  }
  if (pwdCaptcha) {
    pwdCaptcha.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handlePasswordLogin()
    })
  }

  if (btnDevFill) {
    btnDevFill.addEventListener('click', () => {
      pwdUsername.value = 'admin'
      pwdPassword.value = '123456'
      if (pwdErrorMsg) pwdErrorMsg.style.display = 'none'
      if (currentCaptcha?.is_enabled && pwdCaptcha) {
        pwdCaptcha.focus()
      }
    })
  }

  // ── 用户身份同步 ──
  function syncAuth() {
    return accountStore.refresh()
  }

  async function completeLogin(token: TokenInfo, user?: UserInfo) {
    await saveAuthSession(token, user)
    showMainView()
    await syncAuth()
  }

  function renderAccount(state: AccountState) {
    accountBar.dataset.state = state.status
    accountBar.setAttribute('aria-busy', String(state.status === 'loading' || (state.status === 'ready' && state.refreshing)))
    btnQuotaRetry.style.display = state.status === 'ready' && state.refreshError ? 'block' : 'none'
    btnQuotaRetry.title = state.status === 'ready' ? state.refreshError || '' : ''
    if (state.status !== 'ready') {
      acctGuest.style.display = 'none'
      acctUser.style.display = 'none'
      btnShowScan.style.display = 'none'
      acctStatusTitle.textContent = state.status === 'loading' ? '正在确认账户…' : '暂时无法确认账户'
      acctStatusDesc.textContent = state.status === 'loading' ? '正在获取今日额度' : state.message
      return
    }
    const quotaInfo = state.quota
    const quotaStatus = state.refreshing ? '额度更新中…' : state.refreshError ? '额度更新失败' : ''

    if (quotaInfo.is_logged_in) {
      // ─ 已登录态 ─
      acctGuest.style.display   = 'none'
      btnShowScan.style.display = 'none'
      acctUser.style.display    = 'flex'

      const user = quotaInfo.user
      const name = user?.nickname || user?.username || '题本学员'
      acctUserName.textContent = name

      if (user?.avatar) {
        acctAvatarImg.src = user.avatar
        acctAvatarImg.style.display = 'block'
        acctAvatarFallback.style.display = 'none'
      } else {
        acctAvatarImg.style.display = 'none'
        acctAvatarFallback.style.display = 'inline'
      }

      acctQuotaLabel.textContent = quotaStatus || '今日剩余 '
      acctQuotaNum.textContent = quotaStatus ? '' : String(quotaInfo.remaining_quota)
      acctQuotaSuffix.textContent = quotaStatus ? '' : ' 次'
    } else {
      // ─ 未登录态 ─
      acctGuest.style.display   = 'flex'
      btnShowScan.style.display = 'flex'
      acctUser.style.display    = 'none'

      guestQuotaSub.textContent = quotaStatus || `今日剩余 ${quotaInfo.remaining_quota} 次试用`
    }
  }

  // ── 扫码登录流程 ──
  async function startScanLogin() {
    stopPolling()
    const version = scanGeneration
    showScanView()
    scanQrImg.style.display   = 'none'
    scanQrLoading.style.display = 'block'
    scanQrLoading.textContent  = '小程序码生成中…'
    scanMainHint.textContent   = '请使用微信扫描上方小程序码'

    try {
      const qrData = await fetchScanQrcode(BACKEND_BASE)
      if (version !== scanGeneration) return
      currentSceneId = qrData.scene_id
      scanQrImg.src = qrData.qrcode_data_url
      scanQrImg.style.display    = 'block'
      scanQrLoading.style.display = 'none'

      scheduleScanPoll(version)
    } catch (err: any) {
      if (version === scanGeneration) scanQrLoading.textContent = `生成失败：${err?.message || '请重试'}`
    }
  }

  function scheduleScanPoll(version: number) {
    pollTimer = setTimeout(async () => {
      if (version !== scanGeneration || !currentSceneId) return
      try {
        const res = await pollScanStatus(currentSceneId, BACKEND_BASE)
        if (version !== scanGeneration) return
        if (res.status === 'CONFIRMED' && res.token) {
          stopPolling()
          await completeLogin(res.token, res.user)
          return
        }
        if (res.status === 'EXPIRED') {
          stopPolling()
          scanMainHint.textContent = '二维码已过期，请点击重新获取'
          return
        }
      } catch { /* 下轮重试，避免并发轮询 */ }
      if (version === scanGeneration) scheduleScanPoll(version)
    }, 2000)
  }

  function stopPolling() {
    scanGeneration++
    currentSceneId = ''
    if (pollTimer) clearTimeout(pollTimer)
    pollTimer = null
  }

  // 点击失效二维码重新拉取
  scanQrImg.addEventListener('click', () => {
    startScanLogin()
  })

  // ── 事件绑定 ──
  btnShowScan.addEventListener('click', () => {
    switchLoginTab('scan')
  })

  btnBack.addEventListener('click', () => {
    stopPolling()
    showMainView()
  })

  btnScanMock.addEventListener('click', async () => {
    if (!currentSceneId) return
    const version = scanGeneration
    const sceneId = currentSceneId
    btnScanMock.textContent = '确认中…'
    try {
      await mockConfirmScan(sceneId, BACKEND_BASE)
      if (version !== scanGeneration) return
      const res = await pollScanStatus(sceneId, BACKEND_BASE)
      if (version !== scanGeneration) return
      if (res.status === 'CONFIRMED' && res.token) {
        stopPolling()
        await completeLogin(res.token, res.user)
      }
    } catch (e: any) {
      alert(`模拟扫码失败: ${e?.message || e}`)
    } finally {
      btnScanMock.textContent = '⚡ 开发调试：模拟确认扫码'
    }
  })

  btnLogout.addEventListener('click', async () => {
    try { await logoutAuthSession() }
    catch (error) { alert(`已退出本地登录，${error instanceof Error ? error.message : '服务端暂时不可用'}`) }
    finally { await syncAuth() }
  })
  btnAuthRetry.addEventListener('click', () => { void syncAuth() })
  btnQuotaRetry.addEventListener('click', () => { void syncAuth() })

  // 题库链接直达
  document.querySelectorAll('.site-chip').forEach((chip) => {
    chip.addEventListener('click', (e) => {
      e.preventDefault()
      const url = (chip as HTMLElement).dataset.url
      if (url) chrome.tabs.create({ url })
    })
  })

  // 底部导航链接
  const footerLinks: Record<string, string> = {
    'footer-official': LOCAL_SITE_ORIGINS[0]!,
    'footer-service':  `${LOCAL_SITE_ORIGINS[0]}/service`,
    'footer-help':     `${LOCAL_SITE_ORIGINS[0]}/help`,
  }
  Object.entries(footerLinks).forEach(([id, url]) => {
    document.getElementById(id)?.addEventListener('click', (e) => {
      e.preventDefault()
      chrome.tabs.create({ url })
    })
  })

  // ── 初始化 ──
  const unsubscribeAccount = accountStore.subscribe(renderAccount)
  window.addEventListener('pagehide', () => {
    unsubscribeAccount()
    stopPolling()
  }, { once: true })
  void syncAuth()

  // ── 页面内容检测 ──
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
    if (!tab?.id) { showNoContent(); return }

    chrome.tabs.sendMessage(tab.id, { type: 'CHECK_STATUS' }, (res) => {
      if (chrome.runtime.lastError || !res?.hasContent) {
        showNoContent()
      } else {
        showHasContent(res.paperTitle, res.questionCount)
      }
    })
  } catch {
    showNoContent()
  }

  function showNoContent() {
    heroCard.classList.remove('active')
    heroEmpty.style.display = 'flex'
    heroReady.style.display = 'none'
    heroEmptyTitle.textContent = '未检测到做题内容'
    heroEmptyDesc.textContent  = '请打开粉笔、华图或事考帮的做题/错题练习页，页面右侧将自动出现卡片。'
  }

  function showHasContent(title?: string, count?: number) {
    heroCard.classList.add('active')
    heroEmpty.style.display = 'none'
    heroReady.style.display = 'flex'
    readyPaperTitle.textContent = title || '做题内容'
    readyPaperMeta.textContent  = count ? `共 ${count} 道题 · B5 考场版` : 'B5 考场版'
  }

  // ── 排版动作 ──
  btnReformat.addEventListener('click', async () => {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
      if (!tab?.id) return
      chrome.tabs.sendMessage(tab.id, { type: 'START_REFORMAT' }, (res) => {
        if (!chrome.runtime.lastError && res?.success) window.close()
      })
    } catch { /* ignore */ }
  })
})
