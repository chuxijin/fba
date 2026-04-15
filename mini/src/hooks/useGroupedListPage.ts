import { ref } from 'vue'
import { fbaApi } from '@/api/sdk'
import { useTokenStore } from '@/store'
import { exportMiniRenderBook } from '@/utils/renderBook'
import type { ExportScope, RenderBookExportSubmitPayload } from '@/utils/renderBook'
import { isMembershipAccessError } from '@/utils/membershipAccess'
import { toLoginPage } from '@/utils/toLoginPage'

export type GroupMode = 'knowledge_point' | 'bank'

export interface TreeNode {
  id: number | null
  name: string
  count: number
  children: TreeNode[]
  bank_id?: number | null
  expanded?: boolean
}

interface ExportTarget {
  scope: ExportScope
  key: string
  templateKey: 'wrong_question'
  totalQuestionCount: number
}

export interface GroupedListPageConfig {
  pageTitle: string
  sessionType: string
  sourceType: string
  exportTitleSuffix: string
  autoDestroySession?: boolean
  loginPrompt: string
  listTitle: string
  loadingText: string
  errorLogPrefix: string
  emptyIcon: string
  emptyText: string
  primaryColor: string
  gradientFrom: string
  gradientVia: string
  exportBorderColor: string
  exportActiveBg: string
  fetchStatistics: (mode: GroupMode) => Promise<any>
  totalCountGetter: (stats: any) => number
}

export const groupModes: Array<{ key: GroupMode, label: string }> = [
  { key: 'knowledge_point', label: '按知识点' },
  { key: 'bank', label: '按题库' },
]

export function useGroupedListPage(config: GroupedListPageConfig) {
  const tokenStore = useTokenStore()
  const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

  const groupMode = ref<GroupMode>('knowledge_point')
  const activeModeIndex = ref(0)
  const showMembershipModal = ref(false)
  const exportingKey = ref('')
  const showExportPopup = ref(false)
  const exportTarget = ref<ExportTarget | null>(null)
  const groupsMap = ref<Record<GroupMode, TreeNode[]>>({
    knowledge_point: [],
    bank: [],
  })
  const loadingMap = ref<Record<GroupMode, boolean>>({
    knowledge_point: false,
    bank: false,
  })
  const statistics = ref<any>({})
  const expandedKeysMap = ref<Record<GroupMode, Set<string>>>({
    knowledge_point: new Set(),
    bank: new Set(),
  })

  // 导出选择模式
  const exportMode = ref(false)
  const selectedExportKeys = ref<Set<string>>(new Set())

  function ensureLogin(): boolean {
    if (tokenStore.updateNowTime().hasLogin)
      return true
    uni.showToast({ title: config.loginPrompt, icon: 'none' })
    setTimeout(() => toLoginPage(), 300)
    return false
  }

  async function loadData(mode: GroupMode = groupMode.value): Promise<void> {
    if (!ensureLogin())
      return

    loadingMap.value[mode] = true
    try {
      const data = await config.fetchStatistics(mode) as any
      const { groups, ...stats } = data || {}
      statistics.value = stats
      groupsMap.value[mode] = groups || []
    }
    catch (error) {
      console.error(`${config.errorLogPrefix}:`, error)
      uni.showToast({ title: '加载失败', icon: 'none' })
    }
    finally {
      loadingMap.value[mode] = false
    }
  }

  function switchGroupMode(mode: GroupMode): void {
    const nextIndex = groupModes.findIndex(item => item.key === mode)
    if (nextIndex >= 0)
      activeModeIndex.value = nextIndex

    if (groupMode.value === mode)
      return

    groupMode.value = mode
    if (!groupsMap.value[mode].length)
      void loadData(mode)
  }

  function onModeSwiperChange(event: any): void {
    const nextIndex = Number(event?.detail?.current || 0)
    const nextMode = groupModes[nextIndex]?.key
    activeModeIndex.value = nextIndex

    if (!nextMode || nextMode === groupMode.value)
      return

    groupMode.value = nextMode
    if (!groupsMap.value[nextMode].length)
      void loadData(nextMode)
  }

  function goBack(): void {
    const pages = getCurrentPages()
    if (pages.length > 1) {
      uni.navigateBack()
      return
    }
    uni.switchTab({ url: '/pages/mine/index' })
  }

  // 展开/收缩状态

  function getNodeKey(node: TreeNode, mode: GroupMode): string {
    return `${mode}_${node.id ?? ''}_${node.name}`
  }

  function onGroupClick(node: TreeNode, mode: GroupMode): void {
    if (node.children && node.children.length > 0) {
      const key = getNodeKey(node, mode)
      const nextSet = new Set(expandedKeysMap.value[mode])
      if (nextSet.has(key))
        nextSet.delete(key)
      else
        nextSet.add(key)
      expandedKeysMap.value[mode] = nextSet
      return
    }

    startPractice(node, mode)
  }

  async function startPractice(node: TreeNode, mode: GroupMode): Promise<void> {
    const params: Record<string, any> = {
      session_type: config.sessionType,
      practice_name: node.name,
    }
    if (mode === 'bank') {
      if (node.bank_id) {
        params.bank_id = node.bank_id
        if (node.id) params.chapter_id = node.id
      }
      else if (node.id) {
        params.bank_id = node.id
      }
    }
    if (mode === 'knowledge_point')
      params.knowledge_point = [node.name]

    uni.showLoading({ title: '创建会话...' })
    try {
      const session = await fbaApi.qbank.session.create(params as any)
      let url = `/pages/practice/session/index?sessionId=${session.id}&mode=practice`
      if (config.autoDestroySession)
        url += '&autoDestroy=1'
      uni.navigateTo({ url })
    }
    catch (error: any) {
      if (isMembershipAccessError(error)) {
        showMembershipModal.value = true
        return
      }
      console.error(`${config.errorLogPrefix}:`, error)
      uni.showToast({ title: error?.message || '创建失败', icon: 'none' })
    }
    finally {
      uni.hideLoading()
    }
  }

  // 导出

  function getActionKey(node: TreeNode, mode: GroupMode): string {
    return `${mode}:${node.bank_id ?? node.id ?? 0}:${node.name}`
  }

  function isExportingNode(node: TreeNode, mode: GroupMode): boolean {
    return exportingKey.value === getActionKey(node, mode)
  }

  async function exportQuestions(node: TreeNode, mode: GroupMode): Promise<void> {
    if (!ensureLogin())
      return

    const currentKey = getActionKey(node, mode)
    if (exportingKey.value === currentKey)
      return

    if (!node.count) {
      uni.showToast({ title: '当前范围内暂无可导出题目', icon: 'none' })
      return
    }

    exportTarget.value = {
      scope: {
        sourceType: config.sourceType,
        templateKey: 'wrong_question',
        title: `${node.name}${config.exportTitleSuffix}`,
        bankId: mode === 'bank' ? (node.bank_id || node.id) : null,
        chapterId: mode === 'bank' && node.bank_id ? node.id : null,
        knowledgePoint: mode === 'knowledge_point' ? node.name : null,
      } as ExportScope,
      key: currentKey,
      templateKey: 'wrong_question',
      totalQuestionCount: Number(node.count || 0),
    }
    showExportPopup.value = true
  }

  async function submitExport(payload: RenderBookExportSubmitPayload): Promise<void> {
    const target = exportTarget.value
    if (!target)
      return

    const isBatch = batchExportContext.nodes.length > 0

    exportingKey.value = target.key
    try {
      if (isBatch) {
        // 批量导出：并发 collect 每个选中节点，合并去重
        const mode = batchExportContext.mode
        const nodes = batchExportContext.nodes
        const scopes = nodes.map(n => buildNodeScope(n, mode))

        uni.showLoading({ title: `正在筛选题目（${scopes.length}项）...` })

        const results = await Promise.all(
          scopes.map(scope =>
            fbaApi.qbank.question.collect({
              source_type: scope.sourceType,
              bank_id: scope.bankId ?? undefined,
              chapter_id: scope.chapterId ?? undefined,
              knowledge_point: scope.knowledgePoint
                ? (Array.isArray(scope.knowledgePoint) ? scope.knowledgePoint : [scope.knowledgePoint])
                : undefined,
            } as any),
          ),
        )

        const allIds = new Set<number>()
        for (const r of results) {
          const ids = (r as any)?.question_ids || []
          for (const id of ids) allIds.add(id)
        }

        uni.hideLoading()

        if (!allIds.size) {
          uni.showToast({ title: '当前范围内暂无可导出的题目', icon: 'none' })
          return
        }

        await exportMiniRenderBook({
          ...target.scope,
          questionIds: [...allIds],
          settings: payload.settings,
          questionCount: payload.questionCount,
          yearStart: payload.yearStart,
          yearEnd: payload.yearEnd,
        })

        // 导出完成，退出选择模式
        exportMode.value = false
        selectedExportKeys.value = new Set()
      }
      else {
        // 单节点导出（原逻辑）
        await exportMiniRenderBook({
          ...target.scope,
          settings: payload.settings,
          questionCount: payload.questionCount,
          yearStart: payload.yearStart,
          yearEnd: payload.yearEnd,
        })
      }
    }
    catch (error: any) {
      uni.hideLoading()
      if (isMembershipAccessError(error)) {
        showMembershipModal.value = true
      }
    }
    finally {
      if (exportingKey.value === target.key)
        exportingKey.value = ''
      exportTarget.value = null
      batchExportContext.nodes = []
    }
  }

  function handleExportPopupChange(value: boolean): void {
    showExportPopup.value = value
    if (!value)
      exportTarget.value = null
  }

  // 树形辅助

  function flattenTree(
    nodes: TreeNode[],
    mode: GroupMode,
    level = 0,
  ): Array<TreeNode & { level: number, hasChildren: boolean, expanded: boolean }> {
    const result: Array<TreeNode & { level: number, hasChildren: boolean, expanded: boolean }> = []
    const expandedKeys = expandedKeysMap.value[mode]
    for (const node of nodes) {
      const hasChildren = (node.children?.length || 0) > 0
      const expanded = hasChildren && expandedKeys.has(getNodeKey(node, mode))
      result.push({ ...node, level, hasChildren, expanded })
      if (hasChildren && expanded)
        result.push(...flattenTree(node.children, mode, level + 1))
    }
    return result
  }

  function getFlatGroups(mode: GroupMode) {
    return flattenTree(groupsMap.value[mode] || [], mode)
  }

  function decorateTree(nodes: TreeNode[], mode: GroupMode): TreeNode[] {
    const expandedKeys = expandedKeysMap.value[mode]

    return (nodes || []).map((node) => {
      const hasChildren = Boolean(node.children && node.children.length > 0)
      const key = getNodeKey(node, mode)
      const expanded = hasChildren ? expandedKeys.has(key) : false

      return {
        ...node,
        expanded,
        children: hasChildren ? decorateTree(node.children, mode) : [],
      }
    })
  }

  function getTreeGroups(mode: GroupMode): TreeNode[] {
    return decorateTree(groupsMap.value[mode] || [], mode)
  }

  function handleGroupTap(node: TreeNode, mode: GroupMode) {
    onGroupClick(node, mode)
    return false
  }

  // 统计

  function getStatistics(): any {
    return statistics.value
  }

  function getModeTotalCount(mode: GroupMode): number {
    return config.totalCountGetter(statistics.value)
  }

  // 批量导出

  function getNodeId(node: TreeNode): string {
    return `${node.bank_id ?? ''}_${node.id ?? ''}_${node.name}`
  }

  function collectSelectedNodes(
    nodes: TreeNode[],
    keys: Set<string>,
  ): TreeNode[] {
    const result: TreeNode[] = []
    for (const node of nodes) {
      if (keys.has(getNodeId(node))) {
        result.push(node)
        // 选了父节点，跳过所有子节点
        continue
      }
      if (node.children?.length)
        result.push(...collectSelectedNodes(node.children, keys))
    }
    return result
  }

  function buildNodeScope(node: TreeNode, mode: GroupMode): ExportScope {
    const scope: ExportScope = {
      sourceType: config.sourceType as ExportScope['sourceType'],
      templateKey: 'wrong_question',
      title: `${node.name}${config.exportTitleSuffix}`,
    }
    if (mode === 'bank') {
      if (node.bank_id) {
        scope.bankId = node.bank_id
        if (node.id) scope.chapterId = node.id
      } else if (node.id) {
        scope.bankId = node.id
      }
    }
    if (mode === 'knowledge_point')
      scope.knowledgePoint = node.name

    return scope
  }

  function getSelectedNodes(): TreeNode[] {
    const keys = selectedExportKeys.value
    if (!keys.size) return []
    const mode = groupMode.value
    return collectSelectedNodes(groupsMap.value[mode] || [], keys)
  }

  function confirmBatchExport(): void {
    const nodes = getSelectedNodes()
    if (!nodes.length) {
      uni.showToast({ title: '请至少选择一项', icon: 'none' })
      return
    }

    const mode = groupMode.value
    const totalCount = nodes.reduce((sum, n) => sum + (n.count || 0), 0)
    const title = nodes.length === 1
      ? `${nodes[0].name}${config.exportTitleSuffix}`
      : `${config.pageTitle}（${nodes.length}项）`

    exportTarget.value = {
      scope: {
        sourceType: config.sourceType as ExportScope['sourceType'],
        templateKey: 'wrong_question',
        title,
      },
      key: `batch_${Date.now()}`,
      templateKey: 'wrong_question',
      totalQuestionCount: totalCount,
    }

    // 存储选中节点和 mode 供 submitExport 使用
    batchExportContext.nodes = nodes
    batchExportContext.mode = mode

    showExportPopup.value = true
  }

  const batchExportContext: { nodes: TreeNode[], mode: GroupMode } = {
    nodes: [],
    mode: 'knowledge_point',
  }

  return {
    config,
    statusBarHeight,
    groupMode,
    activeModeIndex,
    showMembershipModal,
    showExportPopup,
    exportTarget,
    loadingMap,
    groupModes,
    loadData,
    switchGroupMode,
    onModeSwiperChange,
    goBack,
    onGroupClick,
    startPractice,
    isExportingNode,
    exportQuestions,
    submitExport,
    handleExportPopupChange,
    confirmBatchExport,
    getFlatGroups,
    getTreeGroups,
    handleGroupTap,
    statistics,
    getStatistics,
    getModeTotalCount,
    exportMode,
    selectedExportKeys,
    toggleExportMode() {
      exportMode.value = !exportMode.value
      if (!exportMode.value)
        selectedExportKeys.value = new Set()
    },
    cancelExportMode() {
      exportMode.value = false
      selectedExportKeys.value = new Set()
    },
    onExportSelectChange(nodeId: string, selected: boolean) {
      const next = new Set(selectedExportKeys.value)
      if (selected)
        next.add(nodeId)
      else
        next.delete(nodeId)
      selectedExportKeys.value = next
    },
  }
}

export type UseGroupedListPageReturn = ReturnType<typeof useGroupedListPage>
