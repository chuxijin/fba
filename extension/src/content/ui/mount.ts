import { createApp } from 'vue'
import App from './App.vue'
import rawCss from './style.css?inline'
import { UnifiedPaper, RenderTypographySettings, ImportState } from '../../adapters'

export interface ReformatterAppInstance {
  setPaper(paper: UnifiedPaper): void
  setPaperInfo(title: string, count: number): void
  setImportState(state: ImportState): void
  resetPaper(): void
  openModal(): void
  closeModal(): void
  showLoading(target: 'computer_download' | 'mobile_sync'): void
  showDelivery(options: { qrCodeUrl?: string; savedPath?: string; remainingQuota?: number }): void
  showError(msg: string): void
}

/**
 * 在宿主网页安全挂载独立 Shadow DOM 物理隔离环境并启动 Vue 3 应用
 */
export function mountReformatterApp(handlers: {
  onRequestReformat: () => Promise<void> | void
  onRequestQuickPrint: () => Promise<void> | void
  onDoExport: (settings: RenderTypographySettings, target: 'computer_download' | 'mobile_sync') => Promise<void> | void
  onImportWrong?: () => Promise<void> | void
  onUndoImport?: () => Promise<void> | void
}): ReformatterAppInstance {
  // 1. 查找或创建挂载宿主容器
  let host = document.getElementById('gongkao-reformatter-shadow-host')
  if (host) {
    try {
      host.remove()
    } catch {}
  }

  host = document.createElement('div')
  host.id = 'gongkao-reformatter-shadow-host'
  host.style.position = 'absolute'
  host.style.top = '0'
  host.style.left = '0'
  host.style.width = '0'
  host.style.height = '0'
  host.style.zIndex = '2147483647'

  const parent = document.body || document.documentElement
  parent.appendChild(host)

  // 2. 挂载 Shadow DOM (物理级样式防火墙)
  const shadowRoot = host.attachShadow({ mode: 'open' })

  // 3. 注入全量设计系统 CSS (内部受控，外部完全不污染且不受干扰)
  const styleEl = document.createElement('style')
  styleEl.textContent = rawCss
  shadowRoot.appendChild(styleEl)

  // 4. 创建 Vue 容器并挂载
  const appContainer = document.createElement('div')
  appContainer.id = 'gk-app'
  shadowRoot.appendChild(appContainer)

  const app = createApp(App, {
    onRequestReformat: handlers.onRequestReformat,
    onRequestQuickPrint: handlers.onRequestQuickPrint,
    onDoExport: handlers.onDoExport,
    onImportWrong: handlers.onImportWrong,
    onUndoImport: handlers.onUndoImport,
  })

  const appInstance = app.mount(appContainer) as any

  return {
    setPaper: (paper) => appInstance.setPaper(paper),
    setPaperInfo: (title, count) => appInstance.setPaperInfo(title, count),
    setImportState: (state) => appInstance.setImportState(state),
    resetPaper: () => appInstance.resetPaper(),
    openModal: () => appInstance.openModal(),
    closeModal: () => appInstance.closeModal(),
    showLoading: (target) => appInstance.showLoading(target),
    showDelivery: (options) => appInstance.showDelivery(options),
    showError: (msg) => appInstance.showError(msg),
  }
}
